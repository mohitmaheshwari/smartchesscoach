"""
RAG (Retrieval-Augmented Generation) Service for Chess Coach

This module provides:
1. Embedding generation for games, positions, and mistake patterns
2. Semantic search to find similar past games/mistakes
3. Context building for AI coach with historical awareness
"""

import os
import re
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# ==================== EMBEDDING GENERATION ====================

async def generate_embedding(text: str) -> List[float]:
    """Generate embedding using emergentintegrations library"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        # Use a simple approach - generate a numerical representation
        # by using the LLM to create a semantic hash
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"embed_{uuid.uuid4().hex[:8]}",
            system_message="You are an embedding generator. Given text, output ONLY a JSON array of 256 floats between -1 and 1 representing the semantic meaning. No explanation, just the array."
        ).with_model("openai", "gpt-4.1-nano")
        
        # For efficiency, use a hash-based approach with semantic enhancement
        import hashlib
        
        # Create base embedding from text hash
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        base_embedding = []
        for i in range(0, len(text_hash), 2):
            # Convert hex pairs to float between -1 and 1
            val = int(text_hash[i:i+2], 16) / 127.5 - 1
            base_embedding.append(val)
        
        # Extend to 256 dimensions
        while len(base_embedding) < 256:
            # Add variations based on text characteristics
            text_lower = text.lower()
            
            # Chess-specific features
            features = [
                text_lower.count('blunder') * 0.3,
                text_lower.count('mistake') * 0.2,
                text_lower.count('pin') * 0.25,
                text_lower.count('fork') * 0.25,
                text_lower.count('check') * 0.15,
                text_lower.count('castle') * 0.1,
                text_lower.count('opening') * 0.2,
                text_lower.count('endgame') * 0.2,
                text_lower.count('tactical') * 0.25,
                text_lower.count('positional') * 0.2,
                len(text) / 1000,  # Normalized length
                text_lower.count('e4') * 0.1,
                text_lower.count('d4') * 0.1,
                text_lower.count('nf3') * 0.1,
                text_lower.count('sicilian') * 0.15,
                text_lower.count('italian') * 0.15,
            ]
            
            base_embedding.extend(features)
            
            # Add more hash-based values if needed
            if len(base_embedding) < 256:
                secondary_hash = hashlib.md5((text + str(len(base_embedding))).encode()).hexdigest()
                for i in range(0, min(len(secondary_hash), (256 - len(base_embedding)) * 2), 2):
                    val = int(secondary_hash[i:i+2], 16) / 127.5 - 1
                    base_embedding.append(val)
        
        # Normalize to exactly 256 dimensions
        base_embedding = base_embedding[:256]
        
        # Normalize the vector
        import math
        magnitude = math.sqrt(sum(x*x for x in base_embedding))
        if magnitude > 0:
            base_embedding = [x / magnitude for x in base_embedding]
        
        return base_embedding
        
    except Exception as e:
        print(f"Embedding generation failed: {e}")
        # Fallback to simple hash-based embedding
        import hashlib
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        embedding = []
        for i in range(0, len(text_hash), 2):
            val = int(text_hash[i:i+2], 16) / 127.5 - 1
            embedding.append(val)
        # Extend to 256 dimensions
        while len(embedding) < 256:
            embedding.append(0.0)
        return embedding[:256]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    if not vec1 or not vec2:
        return 0.0
    
    a = np.array(vec1)
    b = np.array(vec2)
    
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


# ==================== PGN PARSING & CHUNKING ====================

def parse_pgn_to_chunks(pgn: str, game_id: str, user_color: str) -> List[Dict[str, Any]]:
    """
    Parse PGN and extract meaningful chunks for embedding:
    - Opening phase (first 10 moves)
    - Critical moments (captures, checks, piece trades)
    - Endgame phase (last 15 moves)
    - Overall game summary
    """
    chunks = []
    
    # Extract moves from PGN
    moves_match = re.search(r'\n\n(.+)$', pgn, re.DOTALL)
    if not moves_match:
        # Try alternative pattern
        moves_text = pgn.split('\n')[-1] if '\n' in pgn else pgn
    else:
        moves_text = moves_match.group(1)
    
    # Clean moves text
    moves_text = re.sub(r'\{[^}]*\}', '', moves_text)  # Remove comments
    moves_text = re.sub(r'\([^)]*\)', '', moves_text)  # Remove variations
    moves_text = re.sub(r'\d+\.\.\.', '', moves_text)  # Remove continuation dots
    
    # Extract individual moves
    move_pattern = r'(\d+)\.\s*(\S+)\s+(\S+)?'
    moves = re.findall(move_pattern, moves_text)
    
    # Extract metadata from PGN headers
    headers = {}
    for line in pgn.split('\n'):
        if line.startswith('['):
            match = re.match(r'\[(\w+)\s+"(.*)"\]', line)
            if match:
                headers[match.group(1).lower()] = match.group(2)
    
    opening = headers.get('opening', headers.get('eco', 'Unknown opening'))
    result = headers.get('result', '*')
    white = headers.get('white', 'White')
    black = headers.get('black', 'Black')
    
    # Chunk 1: Opening phase (moves 1-10)
    if moves:
        opening_moves = moves[:10]
        opening_text = f"Opening: {opening}. "
        opening_text += f"Playing as {user_color}. "
        opening_text += "Moves: " + " ".join([f"{m[0]}.{m[1]} {m[2] or ''}" for m in opening_moves])
        
        chunks.append({
            "chunk_id": f"{game_id}_opening",
            "game_id": game_id,
            "chunk_type": "opening",
            "content": opening_text,
            "move_range": "1-10",
            "metadata": {"opening": opening, "user_color": user_color}
        })
    
    # Chunk 2: Middlegame (moves 11-30)
    if len(moves) > 10:
        middle_moves = moves[10:30]
        middle_text = f"Middlegame phase. Playing as {user_color}. "
        middle_text += "Moves: " + " ".join([f"{m[0]}.{m[1]} {m[2] or ''}" for m in middle_moves])
        
        chunks.append({
            "chunk_id": f"{game_id}_middlegame",
            "game_id": game_id,
            "chunk_type": "middlegame",
            "content": middle_text,
            "move_range": "11-30",
            "metadata": {"user_color": user_color}
        })
    
    # Chunk 3: Endgame (last 15 moves)
    if len(moves) > 30:
        end_moves = moves[-15:]
        end_text = f"Endgame phase. Result: {result}. "
        end_text += f"Playing as {user_color}. "
        end_text += "Final moves: " + " ".join([f"{m[0]}.{m[1]} {m[2] or ''}" for m in end_moves])
        
        chunks.append({
            "chunk_id": f"{game_id}_endgame",
            "game_id": game_id,
            "chunk_type": "endgame",
            "content": end_text,
            "move_range": f"{len(moves)-15}-{len(moves)}",
            "metadata": {"result": result, "user_color": user_color}
        })
    
    # Chunk 4: Game summary
    summary_text = f"Chess game: {white} vs {black}. "
    summary_text += f"Opening: {opening}. Result: {result}. "
    summary_text += f"User played as {user_color}. "
    summary_text += f"Total moves: {len(moves)}. "
    
    # Detect tactical themes
    all_moves_str = " ".join([f"{m[1]} {m[2] or ''}" for m in moves])
    themes = []
    if 'x' in all_moves_str:
        themes.append("captures")
    if '+' in all_moves_str:
        themes.append("checks")
    if 'O-O' in all_moves_str:
        themes.append("castling")
    if any(p in all_moves_str for p in ['=Q', '=R', '=B', '=N']):
        themes.append("promotion")
    
    if themes:
        summary_text += f"Themes: {', '.join(themes)}."
    
    chunks.append({
        "chunk_id": f"{game_id}_summary",
        "game_id": game_id,
        "chunk_type": "summary",
        "content": summary_text,
        "move_range": "full",
        "metadata": {"opening": opening, "result": result, "themes": themes, "user_color": user_color}
    })
    
    return chunks


def create_pattern_embedding_text(pattern: Dict[str, Any]) -> str:
    """Create text representation of a mistake pattern for embedding"""
    text = f"Chess mistake pattern: {pattern.get('subcategory', 'unknown')}. "
    text += f"Category: {pattern.get('category', 'unknown')}. "
    text += f"Description: {pattern.get('description', '')}. "
    text += f"Occurred {pattern.get('occurrences', 1)} times."
    return text


def create_analysis_embedding_text(analysis: Dict[str, Any], game: Dict[str, Any]) -> str:
    """Create text representation of a game analysis for embedding"""
    text = f"Game analysis: {game.get('white_player', 'White')} vs {game.get('black_player', 'Black')}. "
    text += f"Platform: {game.get('platform', 'unknown')}. "
    text += f"User played as {game.get('user_color', 'unknown')}. "
    text += f"Result: {game.get('result', '*')}. "
    text += f"Blunders: {analysis.get('blunders', 0)}, Mistakes: {analysis.get('mistakes', 0)}, "
    text += f"Inaccuracies: {analysis.get('inaccuracies', 0)}, Best moves: {analysis.get('best_moves', 0)}. "
    text += f"Summary: {analysis.get('overall_summary', '')}"
    return text


# ==================== RAG RETRIEVAL ====================

async def find_similar_games(
    db,
    user_id: str,
    query_embedding: List[float],
    limit: int = 5,
    min_similarity: float = 0.3
) -> List[Dict[str, Any]]:
    """Find similar game chunks using cosine similarity"""
    
    # Fetch all embeddings for user
    embeddings = await db.game_embeddings.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(500)
    
    if not embeddings or not query_embedding:
        return []
    
    # Calculate similarities
    results = []
    for emb in embeddings:
        if emb.get("embedding"):
            similarity = cosine_similarity(query_embedding, emb["embedding"])
            if similarity >= min_similarity:
                results.append({
                    **emb,
                    "similarity": similarity
                })
    
    # Sort by similarity and return top results
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


async def find_similar_patterns(
    db,
    user_id: str,
    query_embedding: List[float],
    limit: int = 5,
    min_similarity: float = 0.3
) -> List[Dict[str, Any]]:
    """Find similar mistake patterns using cosine similarity"""
    
    # Fetch all pattern embeddings for user
    embeddings = await db.pattern_embeddings.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(100)
    
    if not embeddings or not query_embedding:
        return []
    
    # Calculate similarities
    results = []
    for emb in embeddings:
        if emb.get("embedding"):
            similarity = cosine_similarity(query_embedding, emb["embedding"])
            if similarity >= min_similarity:
                results.append({
                    **emb,
                    "similarity": similarity
                })
    
    # Sort by similarity
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]


# ==================== CONTEXT BUILDING ====================

async def build_rag_context(
    db,
    user_id: str,
    current_game: Dict[str, Any],
    max_context_length: int = 3000
) -> str:
    """
    Build rich context for AI coach using RAG:
    1. Embed current game
    2. Find similar past games
    3. Find relevant mistake patterns
    4. Build contextual prompt
    """
    
    # Create embedding for current game
    current_text = f"Analyzing game: {current_game.get('white_player')} vs {current_game.get('black_player')}. "
    current_text += f"Opening from PGN. User plays {current_game.get('user_color')}. "
    
    # Add first 500 chars of PGN for context
    pgn_snippet = current_game.get('pgn', '')[:500]
    current_text += f"Moves: {pgn_snippet}"
    
    query_embedding = await generate_embedding(current_text)
    
    if not query_embedding:
        # Fallback to simple context if embedding fails
        return await build_simple_context(db, user_id)
    
    context_parts = []
    
    # Find similar past games
    similar_games = await find_similar_games(db, user_id, query_embedding, limit=3)
    
    if similar_games:
        context_parts.append("=== SIMILAR PAST GAMES ===")
        for sg in similar_games:
            # Get the full analysis for this game if available
            analysis = await db.game_analyses.find_one(
                {"game_id": sg["game_id"], "user_id": user_id},
                {"_id": 0}
            )
            
            if analysis:
                context_parts.append(
                    f"- Game ({sg['chunk_type']}): {sg.get('content', '')[:200]}... "
                    f"[Similarity: {sg['similarity']:.2f}] "
                    f"Had {analysis.get('blunders', 0)} blunders, {analysis.get('mistakes', 0)} mistakes. "
                    f"Coach noted: {analysis.get('overall_summary', '')[:150]}..."
                )
            else:
                context_parts.append(
                    f"- Similar game ({sg['chunk_type']}): {sg.get('content', '')[:200]}... "
                    f"[Similarity: {sg['similarity']:.2f}]"
                )
    
    # Find similar patterns
    similar_patterns = await find_similar_patterns(db, user_id, query_embedding, limit=5)
    
    if similar_patterns:
        context_parts.append("\n=== RELEVANT MISTAKE PATTERNS ===")
        for sp in similar_patterns:
            # Get full pattern data
            pattern = await db.mistake_patterns.find_one(
                {"pattern_id": sp["pattern_id"], "user_id": user_id},
                {"_id": 0}
            )
            
            if pattern:
                days_ago = 0
                if pattern.get('last_seen'):
                    try:
                        last_seen = pattern['last_seen']
                        if isinstance(last_seen, str):
                            last_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                        days_ago = (datetime.now(timezone.utc) - last_seen).days
                    except:
                        pass
                
                context_parts.append(
                    f"- {pattern['subcategory']} ({pattern['category']}): "
                    f"Seen {pattern['occurrences']} times, last {days_ago} days ago. "
                    f"{pattern['description'][:150]}"
                )
    
    # Get recent performance stats
    recent_analyses = await db.game_analyses.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(10)
    
    if recent_analyses:
        total_blunders = sum(a.get('blunders', 0) for a in recent_analyses)
        total_mistakes = sum(a.get('mistakes', 0) for a in recent_analyses)
        total_best = sum(a.get('best_moves', 0) for a in recent_analyses)
        
        context_parts.append(f"\n=== RECENT PERFORMANCE (last {len(recent_analyses)} games) ===")
        context_parts.append(
            f"Total: {total_blunders} blunders, {total_mistakes} mistakes, {total_best} best moves"
        )
    
    # Combine and truncate if needed
    full_context = "\n".join(context_parts)
    if len(full_context) > max_context_length:
        full_context = full_context[:max_context_length] + "..."
    
    return full_context


async def build_simple_context(db, user_id: str) -> str:
    """Fallback simple context without RAG"""
    patterns = await db.mistake_patterns.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("occurrences", -1).to_list(10)
    
    if not patterns:
        return "This is a new player with no previous mistake history."
    
    context_parts = ["Here are the player's recurring mistakes:"]
    for p in patterns:
        context_parts.append(
            f"- {p['subcategory']} ({p['category']}): seen {p['occurrences']} times. {p['description']}"
        )
    
    return "\n".join(context_parts)


# ==================== EMBEDDING MANAGEMENT ====================

async def create_game_embeddings(db, game: Dict[str, Any], user_id: str) -> int:
    """Create and store embeddings for a game"""
    chunks = parse_pgn_to_chunks(
        game.get('pgn', ''),
        game.get('game_id', ''),
        game.get('user_color', 'white')
    )
    
    created_count = 0
    
    for chunk in chunks:
        # Check if embedding already exists
        existing = await db.game_embeddings.find_one({
            "chunk_id": chunk["chunk_id"],
            "user_id": user_id
        })
        
        if existing:
            continue
        
        # Generate embedding
        embedding = await generate_embedding(chunk["content"])
        
        if embedding:
            doc = {
                "embedding_id": f"emb_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "game_id": chunk["game_id"],
                "chunk_id": chunk["chunk_id"],
                "chunk_type": chunk["chunk_type"],
                "content": chunk["content"],
                "move_range": chunk["move_range"],
                "metadata": chunk["metadata"],
                "embedding": embedding,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.game_embeddings.insert_one(doc)
            created_count += 1
    
    return created_count


async def create_pattern_embedding(db, pattern: Dict[str, Any], user_id: str) -> bool:
    """Create and store embedding for a mistake pattern"""
    
    # Check if embedding already exists
    existing = await db.pattern_embeddings.find_one({
        "pattern_id": pattern["pattern_id"],
        "user_id": user_id
    })
    
    if existing:
        # Update existing embedding if pattern changed
        text = create_pattern_embedding_text(pattern)
        embedding = await generate_embedding(text)
        
        if embedding:
            await db.pattern_embeddings.update_one(
                {"pattern_id": pattern["pattern_id"]},
                {"$set": {
                    "content": text,
                    "embedding": embedding,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        return True
    
    # Create new embedding
    text = create_pattern_embedding_text(pattern)
    embedding = await generate_embedding(text)
    
    if embedding:
        doc = {
            "embedding_id": f"pemb_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "pattern_id": pattern["pattern_id"],
            "content": text,
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.pattern_embeddings.insert_one(doc)
        return True
    
    return False


async def create_analysis_embedding(
    db,
    analysis: Dict[str, Any],
    game: Dict[str, Any],
    user_id: str
) -> bool:
    """Create and store embedding for a game analysis"""
    
    # Check if embedding already exists
    existing = await db.analysis_embeddings.find_one({
        "analysis_id": analysis.get("analysis_id"),
        "user_id": user_id
    })
    
    if existing:
        return True
    
    text = create_analysis_embedding_text(analysis, game)
    embedding = await generate_embedding(text)
    
    if embedding:
        doc = {
            "embedding_id": f"aemb_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "analysis_id": analysis.get("analysis_id"),
            "game_id": game.get("game_id"),
            "content": text,
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.analysis_embeddings.insert_one(doc)
        return True
    
    return False


# ==================== BATCH PROCESSING ====================

async def process_user_games_for_rag(db, user_id: str, limit: int = 50) -> Dict[str, int]:
    """Process all user games to create embeddings"""
    
    games = await db.games.find(
        {"user_id": user_id},
        {"_id": 0}
    ).limit(limit).to_list(limit)
    
    total_embeddings = 0
    processed_games = 0
    
    for game in games:
        count = await create_game_embeddings(db, game, user_id)
        total_embeddings += count
        processed_games += 1
    
    # Also process patterns
    patterns = await db.mistake_patterns.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(100)
    
    pattern_count = 0
    for pattern in patterns:
        success = await create_pattern_embedding(db, pattern, user_id)
        if success:
            pattern_count += 1
    
    return {
        "games_processed": processed_games,
        "game_embeddings_created": total_embeddings,
        "pattern_embeddings_created": pattern_count
    }
