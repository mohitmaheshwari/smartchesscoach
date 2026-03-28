# Chess Coach 2.0 - Architecture for 9.5/10

## Vision Statement
A self-learning chess coach that evolves with every user interaction, provides personalized identity-based coaching, and creates viral growth through shareable chess personalities.

---

## What Makes This 9.5/10

| Gap in Current System | 9.5 Solution |
|-----------------------|--------------|
| Pattern matching has 0.08% effectiveness | ML-based mistake classification |
| "Self-learning" isn't visible to users | Explicit "I learned from you" moments |
| No viral mechanics | Shareable Identity Cards, leaderboards |
| 65 scattered collections | 12 unified collections |
| 150k line files | Micro-frontend architecture |
| Rule-based coaching | LLM with RAG + user memory |
| No proven improvement loop | Measurable skill tracking with proof |

---

## 1. SYSTEM OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CHESS COACH 2.0                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   IDENTITY   │    │   LEARNING   │    │    VIRAL     │          │
│  │    ENGINE    │    │    ENGINE    │    │   ENGINE     │          │
│  │              │    │              │    │              │          │
│  │ • Archetype  │    │ • ML Mistake │    │ • Share Card │          │
│  │ • Evolution  │    │   Classifier │    │ • Leaderboard│          │
│  │ • Traits     │    │ • Feedback   │    │ • Challenges │          │
│  │ • Milestones │    │   Loop       │    │ • Social     │          │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘          │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                       │
│                    ┌────────▼────────┐                              │
│                    │   COACH BRAIN   │                              │
│                    │                 │                              │
│                    │  LLM + RAG +    │                              │
│                    │  User Memory +  │                              │
│                    │  Stockfish      │                              │
│                    └────────┬────────┘                              │
│                             │                                       │
│         ┌───────────────────┼───────────────────┐                   │
│         │                   │                   │                   │
│  ┌──────▼───────┐    ┌──────▼───────┐    ┌──────▼───────┐          │
│  │   ANALYSIS   │    │   TRAINING   │    │   PROGRESS   │          │
│  │   SERVICE    │    │   SERVICE    │    │   SERVICE    │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. ML-BASED LEARNING ENGINE

### 2.1 Mistake Classification Model

Replace rule-based pattern matching with ML:

```
┌─────────────────────────────────────────────────────────────────┐
│                 MISTAKE CLASSIFIER (ML)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT:                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • Position FEN                                           │    │
│  │ • Move played vs Best move                               │    │
│  │ • Eval drop magnitude                                    │    │
│  │ • Piece positions (encoded)                              │    │
│  │ • Game phase                                             │    │
│  │ • Time remaining (if available)                          │    │
│  │ • Player's historical weakness profile                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           TRANSFORMER ENCODER                            │    │
│  │                                                          │    │
│  │   Position Embedding + Move Embedding + Context          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  OUTPUT:                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • Mistake Category (33 classes) + confidence             │    │
│  │ • Root Cause (why this mistake happened)                 │    │
│  │ • Recommended Training Type                              │    │
│  │ • Similar Historical Mistakes (for pattern detection)    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Model Architecture:**
```python
# Mistake Classifier - PyTorch Architecture

class ChessMistakeClassifier(nn.Module):
    def __init__(self):
        self.position_encoder = ChessPositionEncoder(d_model=256)
        self.move_encoder = MoveEncoder(d_model=128)
        self.context_encoder = ContextEncoder(d_model=64)  # phase, time, history
        
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=448, nhead=8),
            num_layers=4
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(448, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 33)  # 33 mistake categories
        )
        
        self.root_cause_head = nn.Linear(448, 64)  # Embedding for RAG lookup
        
    def forward(self, position, move, context):
        pos_emb = self.position_encoder(position)
        move_emb = self.move_encoder(move)
        ctx_emb = self.context_encoder(context)
        
        combined = torch.cat([pos_emb, move_emb, ctx_emb], dim=-1)
        encoded = self.transformer(combined)
        
        category = self.classifier(encoded)
        root_cause_emb = self.root_cause_head(encoded)
        
        return category, root_cause_emb
```

**Training Data:**
- Source: Lichess open database (4B+ games)
- Filter: Games with analysis, mistakes where eval drops > 100cp
- Labels: Bootstrap from current 33 tags, then refine with user feedback
- Size: ~10M mistake examples

### 2.2 Continuous Learning Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│              CONTINUOUS LEARNING PIPELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   USER CORRECTION                                                │
│   "This wasn't a fork, I missed the pin"                        │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │  FEEDBACK QUEUE     │  (Real-time collection)               │
│   └──────────┬──────────┘                                       │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │  VALIDATION         │  (Verify correction makes sense)      │
│   │  • Stockfish check  │                                       │
│   │  • Pattern verify   │                                       │
│   └──────────┬──────────┘                                       │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │  TRAINING BUFFER    │  (Batch corrections)                  │
│   │  Min: 100 examples  │                                       │
│   └──────────┬──────────┘                                       │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │  FINE-TUNING JOB    │  (Nightly or on-demand)              │
│   │  • LoRA fine-tune   │                                       │
│   │  • A/B test new     │                                       │
│   │    model            │                                       │
│   └──────────┬──────────┘                                       │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │  MODEL REGISTRY     │                                       │
│   │  • v1.0 (baseline)  │                                       │
│   │  • v1.1 (current)   │◄── Promote if better                 │
│   │  • v1.2 (candidate) │                                       │
│   └─────────────────────┘                                       │
│                                                                  │
│   VISIBLE TO USER:                                               │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  "Thanks for the correction! I've learned that in       │   │
│   │   positions like this, it's usually a pin, not a fork.  │   │
│   │   I'll remember this for future analysis."              │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Position Similarity Engine

For finding "positions like this":

```python
# Vector-based position similarity

class PositionSimilarityEngine:
    def __init__(self):
        self.encoder = PretrainedChessEncoder()  # Fine-tuned on Lichess
        self.vector_db = QdrantClient()  # Or Pinecone/Weaviate
        
    async def find_similar_mistakes(self, position_fen: str, k: int = 5):
        # Encode position to vector
        embedding = self.encoder.encode(position_fen)
        
        # Search vector DB
        results = await self.vector_db.search(
            collection="mistake_positions",
            query_vector=embedding,
            limit=k,
            filter={"user_id": user_id}  # Personal mistakes first
        )
        
        return results
    
    async def index_mistake(self, position_fen: str, mistake_data: dict):
        embedding = self.encoder.encode(position_fen)
        await self.vector_db.upsert(
            collection="mistake_positions",
            points=[{
                "id": mistake_data["id"],
                "vector": embedding,
                "payload": mistake_data
            }]
        )
```

---

## 3. IDENTITY ENGINE 2.0

### 3.1 Dynamic Archetype System

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARCHETYPE ENGINE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUTS (from last 50 games):                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ • Piece activity patterns (which pieces you use most)   │    │
│  │ • Pawn structure preferences                            │    │
│  │ • King safety vs King activity tradeoffs                │    │
│  │ • Time usage patterns                                   │    │
│  │ • Opening repertoire diversity                          │    │
│  │ • Endgame conversion rate                               │    │
│  │ • Tactical vs Positional mistake ratio                  │    │
│  │ • Risk-taking in equal positions                        │    │
│  │ • Comeback rate from losing positions                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              ARCHETYPE CLASSIFIER                        │    │
│  │                                                          │    │
│  │   Primary Archetype (1 of 12):                          │    │
│  │   ├── The Tactician      (loves combinations)           │    │
│  │   ├── The Strategist     (long-term planning)           │    │
│  │   ├── The Attacker       (aggressive, king-hunt)        │    │
│  │   ├── The Defender       (solid, counter-punch)         │    │
│  │   ├── The Endgame Artist (converts small edges)         │    │
│  │   ├── The Opening Expert (deep preparation)             │    │
│  │   ├── The Improviser     (creative, unpredictable)      │    │
│  │   ├── The Grinder        (plays on, never resigns)      │    │
│  │   ├── The Speed Demon    (fast, intuitive)              │    │
│  │   ├── The Calculator     (deep, precise)                │    │
│  │   ├── The Transformer    (style changes mid-game)       │    │
│  │   └── The Universal      (balanced, adaptable)          │    │
│  │                                                          │    │
│  │   Secondary Traits (2-3):                               │    │
│  │   • "Knight whisperer"   (above-average knight play)    │    │
│  │   • "Time scrambler"     (performs well in zeitnot)     │    │
│  │   • "Exchange sacrifice" (frequently sacs exchange)     │    │
│  │   • "Fortress builder"   (excellent defensive setups)   │    │
│  │   • etc.                                                │    │
│  │                                                          │    │
│  │   Weakness Signature:                                   │    │
│  │   • Primary leak (e.g., "Rook endgames")               │    │
│  │   • Trigger condition (e.g., "When ahead on time")     │    │
│  │   • Improvement trend (↑/↓/→)                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Identity Evolution Tracking

```python
# Identity snapshot with rich metrics

class IdentitySnapshot:
    snapshot_id: str
    user_id: str
    created_at: datetime
    games_analyzed: int
    
    # Core Identity
    primary_archetype: str  # "The Tactician"
    archetype_confidence: float  # 0.85
    secondary_traits: List[str]  # ["Knight whisperer", "Time scrambler"]
    
    # Detailed Metrics
    metrics: {
        "tactical_accuracy": 0.72,
        "positional_understanding": 0.65,
        "endgame_conversion": 0.58,
        "opening_preparation": 0.81,
        "time_management": 0.45,
        "resilience": 0.70,  # comeback rate
        "consistency": 0.62,
    }
    
    # Weakness Profile
    weakness: {
        "primary": "rook_endgames",
        "secondary": ["opposite_colored_bishops", "time_pressure"],
        "improving": ["knight_forks"],  # was weak, getting better
        "trigger": "when_ahead_on_clock",
    }
    
    # Style DNA (for comparison)
    style_vector: List[float]  # 64-dim embedding for similarity
    
    # Narrative
    one_liner: str  # "A creative tactician who struggles in technical endgames"
    evolution_story: str  # "Over the last month, you've become more patient..."
```

### 3.3 Evolution Narrative Generator

```python
async def generate_evolution_narrative(
    old_snapshot: IdentitySnapshot,
    new_snapshot: IdentitySnapshot
) -> str:
    """
    Generate a compelling narrative about how the player has evolved.
    Uses LLM with structured data.
    """
    
    changes = compute_changes(old_snapshot, new_snapshot)
    
    prompt = f"""
    You are a wise chess coach writing a personal note to your student.
    
    STUDENT PROFILE:
    - Current archetype: {new_snapshot.primary_archetype}
    - Previous archetype: {old_snapshot.primary_archetype}
    - Games between snapshots: {new_snapshot.games_analyzed - old_snapshot.games_analyzed}
    
    CHANGES OBSERVED:
    - Tactical accuracy: {changes['tactical_accuracy']:+.0%}
    - Positional understanding: {changes['positional_understanding']:+.0%}
    - Endgame conversion: {changes['endgame_conversion']:+.0%}
    - Time management: {changes['time_management']:+.0%}
    
    STYLE SHIFT:
    - {changes['style_shift_description']}
    
    WEAKNESS CHANGES:
    - Old primary weakness: {old_snapshot.weakness['primary']}
    - New primary weakness: {new_snapshot.weakness['primary']}
    - Improving areas: {new_snapshot.weakness['improving']}
    
    Write a 2-3 sentence personal observation about their evolution.
    Be specific, warm, and insightful. Reference concrete changes.
    Don't be generic. Sound like a human coach who knows them.
    """
    
    response = await llm.generate(prompt)
    return response

# Example output:
# "You've evolved from a pure tactician into something more nuanced. 
#  Your positional play jumped 12% this month - I see you're thinking 
#  more about pawn structures now. The rook endgames are still tricky, 
#  but your knight play? That's becoming a real weapon."
```

---

## 4. COACH BRAIN (LLM + RAG)

### 4.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       COACH BRAIN                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    MEMORY LAYERS                         │    │
│  │                                                          │    │
│  │  L1: Session Memory (current conversation)              │    │
│  │      • Last 20 messages                                 │    │
│  │      • Current game being discussed                     │    │
│  │                                                          │    │
│  │  L2: User Memory (permanent, per-user)                  │    │
│  │      • Identity snapshot                                │    │
│  │      • Historical weaknesses                            │    │
│  │      • Past corrections they've made                    │    │
│  │      • Preferred coaching style                         │    │
│  │      • Goals they've stated                             │    │
│  │                                                          │    │
│  │  L3: Knowledge Base (RAG)                               │    │
│  │      • Chess theory (openings, endgames, strategy)      │    │
│  │      • Common mistake patterns                          │    │
│  │      • Training recommendations                         │    │
│  │      • Famous game examples                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  CONTEXT ASSEMBLER                       │    │
│  │                                                          │    │
│  │  For each user query:                                   │    │
│  │  1. Retrieve relevant L1 (recent conversation)          │    │
│  │  2. Inject L2 (user profile, identity, weaknesses)      │    │
│  │  3. RAG search L3 for relevant knowledge                │    │
│  │  4. Add current position analysis (Stockfish)           │    │
│  │  5. Assemble final prompt                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     LLM ROUTER                           │    │
│  │                                                          │    │
│  │  Route to appropriate model:                            │    │
│  │  • Quick questions → GPT-4o-mini (fast, cheap)          │    │
│  │  • Deep analysis → GPT-4o (thorough)                    │    │
│  │  • Identity narrative → Claude (better writing)         │    │
│  │  • Position eval → Stockfish (accurate)                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Prompt Engineering for Personalization

```python
COACH_SYSTEM_PROMPT = """
You are a personal chess coach with deep knowledge of your student.

STUDENT PROFILE:
{identity_snapshot}

COACHING STYLE:
- Be direct and specific, not generic
- Reference their actual games and patterns
- Use their archetype to frame advice
- Acknowledge their strengths before addressing weaknesses
- Connect current position to their historical patterns

STUDENT'S STATED GOALS:
{user_goals}

THINGS THEY'VE TOLD YOU BEFORE:
{user_memory}

THEIR CURRENT WEAKNESSES (from data):
{weakness_profile}

POSITIONS WHERE THEY'VE MADE SIMILAR MISTAKES:
{similar_mistakes}

Remember: You KNOW this student. Don't give generic advice.
Reference specific patterns you've seen in their games.
"""
```

### 4.3 Socratic Questioning Engine

```python
class SocraticEngine:
    """
    Generate questions that guide discovery, not just answers.
    """
    
    async def generate_reflection_question(
        self,
        position: str,
        played_move: str,
        best_move: str,
        user_identity: IdentitySnapshot
    ) -> str:
        
        # Don't ask about what they're already good at
        skip_topics = user_identity.metrics_above_threshold(0.75)
        
        # Focus on their weaknesses
        focus_topics = user_identity.weakness["primary"]
        
        prompt = f"""
        Position: {position}
        They played: {played_move}
        Best was: {best_move}
        
        Their weakness: {focus_topics}
        Don't ask about: {skip_topics}
        
        Generate a Socratic question that:
        1. Doesn't reveal the answer
        2. Guides them to discover it
        3. Connects to their known weakness pattern
        4. Is specific to this position, not generic
        
        Examples of BAD questions:
        - "What do you think the best move is?" (too generic)
        - "Did you consider all checks?" (leading)
        
        Examples of GOOD questions:
        - "Your knight is very active here. What happens if White plays Bb5?"
        - "You played quickly here. What was Black's threat?"
        """
        
        return await llm.generate(prompt)
```

---

## 5. VIRAL ENGINE

### 5.1 Shareable Identity Card

```
┌─────────────────────────────────────────────────────────────────┐
│                   SHAREABLE IDENTITY CARD                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                                                          │    │
│  │   ♞ THE TACTICIAN ♞                                     │    │
│  │   @username • 1847 Rapid                                │    │
│  │                                                          │    │
│  │   ┌────────────────────────────────────┐                │    │
│  │   │ ████████████░░░░ Tactics    78%    │                │    │
│  │   │ ██████████░░░░░░ Strategy   65%    │                │    │
│  │   │ ████████░░░░░░░░ Endgames   52%    │                │    │
│  │   │ ██████████████░░ Openings   82%    │                │    │
│  │   └────────────────────────────────────┘                │    │
│  │                                                          │    │
│  │   SPECIAL TRAITS:                                       │    │
│  │   🗡️ Knight Whisperer • ⚡ Speed Demon                  │    │
│  │                                                          │    │
│  │   KRYPTONITE: Rook Endgames                             │    │
│  │                                                          │    │
│  │   "A creative attacker who sees combinations            │    │
│  │    others miss, but sometimes forgets the               │    │
│  │    basics in technical positions."                      │    │
│  │                                                          │    │
│  │   ─────────────────────────────────────                 │    │
│  │   Discover your Chess Identity at chesscoach.ai        │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  SHARE TO:                                                       │
│  [Twitter] [Reddit] [Discord] [Copy Link] [Download PNG]        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Social Features

```python
# Viral mechanics

class ViralEngine:
    
    async def generate_share_card(self, user_id: str) -> ShareCard:
        """Generate a beautiful, shareable identity card."""
        identity = await self.get_identity(user_id)
        
        return ShareCard(
            archetype=identity.primary_archetype,
            username=identity.username,
            rating=identity.rating,
            metrics=identity.metrics,
            traits=identity.secondary_traits,
            weakness=identity.weakness["primary"],
            tagline=identity.one_liner,
            share_url=f"https://chesscoach.ai/identity/{user_id}"
        )
    
    async def compare_with_friend(self, user_id: str, friend_id: str) -> Comparison:
        """Compare two players' identities."""
        me = await self.get_identity(user_id)
        friend = await self.get_identity(friend_id)
        
        return Comparison(
            style_similarity=cosine_similarity(me.style_vector, friend.style_vector),
            complementary_strengths=find_complementary(me, friend),
            who_wins_what={
                "tactics": me if me.metrics["tactical_accuracy"] > friend.metrics["tactical_accuracy"] else friend,
                "endgames": me if me.metrics["endgame_conversion"] > friend.metrics["endgame_conversion"] else friend,
                # ...
            },
            fun_insight=generate_fun_comparison(me, friend)
        )
    
    async def get_leaderboard(self, category: str) -> List[LeaderboardEntry]:
        """Leaderboards by category."""
        categories = {
            "tacticians": sort_by("tactical_accuracy"),
            "grinders": sort_by("resilience"),
            "speed_demons": sort_by("blitz_performance"),
            "improvers": sort_by("improvement_rate"),
        }
        return await self.db.get_top(categories[category], limit=100)
    
    async def create_challenge(self, challenger_id: str, challenged_id: str, type: str) -> Challenge:
        """Challenge a friend to prove who's better at X."""
        challenges = {
            "tactics_duel": "Solve 10 tactics, fastest wins",
            "endgame_showdown": "Convert 5 endgames, most accurate wins",
            "style_clash": "Play 3 games, coach rates who played to their archetype best"
        }
        return Challenge(type=type, description=challenges[type])
```

### 5.3 Weekly Digest (Email)

```python
async def generate_weekly_digest(user_id: str) -> WeeklyDigest:
    """
    Generate a weekly email that users actually want to read.
    """
    
    # Get user data
    week_games = await get_games_this_week(user_id)
    identity = await get_identity(user_id)
    identity_last_week = await get_identity_snapshot(user_id, days_ago=7)
    
    # Compute highlights
    highlights = {
        "games_played": len(week_games),
        "best_game": find_best_game(week_games),  # Highest accuracy
        "biggest_improvement": compute_biggest_improvement(identity, identity_last_week),
        "weakness_progress": compute_weakness_progress(identity),
        "archetype_shift": detect_archetype_shift(identity, identity_last_week),
    }
    
    # Generate narrative with LLM
    narrative = await generate_digest_narrative(highlights, identity)
    
    # Recommended focus for next week
    focus = await generate_weekly_focus(identity)
    
    return WeeklyDigest(
        subject=f"Your Chess Week: {highlights['games_played']} games, {highlights['biggest_improvement']}",
        narrative=narrative,
        highlights=highlights,
        recommended_focus=focus,
        share_card=await generate_share_card(user_id),
        cta="Continue your journey →"
    )
```

---

## 6. DATA ARCHITECTURE (SIMPLIFIED)

### 6.1 From 65 Collections → 12 Collections

```
CURRENT (65 collections)          →    NEW (12 collections)
─────────────────────────────────      ─────────────────────────────

users                                  users
  └── user_adaptive_plans       →        └── (embedded) adaptive_plan
  └── user_sessions             →        └── (embedded) sessions
  └── user_ratings              →        └── (embedded) rating_history

games                                  games
  └── game_analyses             →        └── (embedded) analysis
  └── game_embeddings           →        └── (embedded) embedding
  └── game_coach_summaries      →        └── (embedded) coach_summary

identity_snapshots                     identity
player_identity                 →        └── (embedded) snapshots[]
                                         └── (embedded) current

coach_memory                           coach_conversations
coach_messages                  →        └── messages[]
coach_sessions                          └── memory
coach_states                            └── state

smart_patterns                         learning
learned_rules                   →        └── patterns[]
pattern_feedback                        └── feedback[]
tag_correction_patterns                 └── corrections[]
concrete_patterns                       └── model_versions[]

mistake_cards                          training
training_progress               →        └── mistake_cards[]
habit_tracking                          └── progress
mission_sessions                        └── habits
                                        └── missions[]

notifications                          notifications (keep simple)

progress_snapshots                     progress
behavioral_reports              →        └── snapshots[]
cognitive_gap_history                   └── behavioral[]
                                        └── cognitive[]

opening_knowledge                      knowledge_base
theory_modules                  →        └── openings
                                        └── theory
                                        └── puzzles

-- VECTOR STORES (separate) --
position_embeddings                    qdrant: positions
mistake_embeddings              →      qdrant: mistakes
```

### 6.2 Core Schemas

```python
# users collection
{
    "_id": ObjectId,
    "user_id": "user_xxx",
    "email": "...",
    "lichess_username": "...",
    "created_at": datetime,
    
    # Embedded identity (denormalized for fast access)
    "identity": {
        "current": IdentitySnapshot,
        "history": [IdentitySnapshot],  # Last 12 snapshots
    },
    
    # Settings & preferences
    "preferences": {
        "coaching_style": "socratic",  # or "direct"
        "notification_frequency": "daily",
        "goals": ["reach_1800", "improve_endgames"]
    },
    
    # Subscription
    "subscription": {
        "plan": "pro",
        "expires_at": datetime
    }
}

# games collection  
{
    "_id": ObjectId,
    "game_id": "game_xxx",
    "user_id": "user_xxx",
    "pgn": "...",
    "imported_at": datetime,
    
    # Embedded analysis (no separate collection)
    "analysis": {
        "stockfish": {...},
        "mistakes": [{
            "move_number": 15,
            "played": "Nf3",
            "best": "Bxc6",
            "eval_drop": 245,
            "category": "tactical_oversight",
            "category_confidence": 0.87,
            "root_cause_embedding": [0.1, 0.2, ...],  # For similarity search
            "tags": ["missed_pin", "piece_safety"],
            "theory_links": ["pins_and_skewers"]
        }],
        "phase_breakdown": {...},
        "accuracy": 72.5
    },
    
    # Coach's take on the game
    "coach_summary": {
        "narrative": "...",
        "key_moment": 15,
        "lesson": "..."
    }
}

# learning collection (replaces smart_patterns, learned_rules, etc.)
{
    "_id": ObjectId,
    "type": "global",  # or "user_xxx" for personal patterns
    
    "patterns": [{
        "pattern_id": "pat_xxx",
        "category": "tactical_oversight",
        "match_criteria": {...},
        "explanation_template": "...",
        "confidence": 0.85,
        "match_count": 127,
        "created_from": "user_feedback",  # or "training_data"
        "created_at": datetime
    }],
    
    "model_versions": [{
        "version": "1.2.0",
        "accuracy": 0.82,
        "deployed_at": datetime,
        "trained_on_samples": 150000
    }],
    
    "pending_feedback": [{
        "position_fen": "...",
        "original_category": "fork",
        "corrected_category": "pin",
        "user_id": "user_xxx",
        "submitted_at": datetime
    }]
}
```

---

## 7. SERVICES ARCHITECTURE

### 7.1 Clean Service Boundaries

```
/backend
├── main.py                    # FastAPI app, minimal routing
├── config.py                  # All configuration
├── dependencies.py            # Dependency injection
│
├── api/                       # API layer (thin)
│   ├── v1/
│   │   ├── auth.py           # ~100 lines
│   │   ├── games.py          # ~150 lines
│   │   ├── coach.py          # ~200 lines
│   │   ├── identity.py       # ~100 lines
│   │   ├── training.py       # ~150 lines
│   │   ├── social.py         # ~100 lines (viral features)
│   │   └── webhooks.py       # ~50 lines
│   └── __init__.py
│
├── services/                  # Business logic
│   ├── analysis/
│   │   ├── stockfish_service.py
│   │   ├── mistake_classifier.py      # ML model wrapper
│   │   └── position_similarity.py     # Vector search
│   │
│   ├── identity/
│   │   ├── archetype_engine.py
│   │   ├── evolution_tracker.py
│   │   └── narrative_generator.py
│   │
│   ├── coach/
│   │   ├── brain.py                   # LLM orchestration
│   │   ├── memory.py                  # User memory management
│   │   ├── socratic_engine.py
│   │   └── rag_retriever.py
│   │
│   ├── learning/
│   │   ├── feedback_processor.py
│   │   ├── model_trainer.py           # Fine-tuning pipeline
│   │   └── pattern_matcher.py
│   │
│   ├── training/
│   │   ├── puzzle_recommender.py
│   │   ├── weakness_analyzer.py
│   │   └── progress_tracker.py
│   │
│   └── viral/
│       ├── share_card_generator.py
│       ├── leaderboard_service.py
│       ├── challenge_service.py
│       └── digest_generator.py
│
├── models/                    # Pydantic models
│   ├── user.py
│   ├── game.py
│   ├── identity.py
│   └── ...
│
├── ml/                        # ML models
│   ├── mistake_classifier/
│   │   ├── model.py
│   │   ├── train.py
│   │   └── inference.py
│   └── position_encoder/
│       ├── model.py
│       └── inference.py
│
└── infrastructure/            # External services
    ├── database.py            # MongoDB
    ├── vector_store.py        # Qdrant
    ├── llm_client.py          # OpenAI/Anthropic
    ├── cache.py               # Redis
    └── queue.py               # Background jobs
```

### 7.2 Service Communication

```python
# Dependency injection pattern

from fastapi import Depends
from functools import lru_cache

class ServiceContainer:
    """Central service container for dependency injection."""
    
    def __init__(self):
        # Infrastructure
        self.db = MongoDBClient()
        self.vector_store = QdrantClient()
        self.llm = LLMClient()
        self.cache = RedisCache()
        
        # Services (injected with infrastructure)
        self.analysis = AnalysisService(self.db, self.vector_store)
        self.identity = IdentityService(self.db, self.llm)
        self.coach = CoachService(self.db, self.llm, self.identity)
        self.learning = LearningService(self.db, self.vector_store)
        self.viral = ViralService(self.db, self.identity)

@lru_cache()
def get_container() -> ServiceContainer:
    return ServiceContainer()

# In API routes
@router.get("/identity/card")
async def get_identity_card(
    user: User = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container)
):
    return await container.viral.generate_share_card(user.user_id)
```

---

## 8. FRONTEND ARCHITECTURE

### 8.1 Component Structure

```
/frontend/src
├── app/                       # Next.js 14 app router
│   ├── (auth)/
│   │   ├── login/
│   │   └── signup/
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── page.tsx          # Dashboard home
│   │   ├── games/
│   │   │   ├── page.tsx      # Games list
│   │   │   └── [id]/         # Game analysis
│   │   ├── identity/
│   │   │   ├── page.tsx      # Identity overview
│   │   │   └── share/        # Shareable card
│   │   ├── coach/
│   │   │   ├── page.tsx      # Coach chat
│   │   │   └── play/         # Play with coach
│   │   ├── training/
│   │   │   ├── page.tsx      # Training hub
│   │   │   └── puzzles/
│   │   └── progress/
│   │       └── page.tsx
│   └── api/                   # API routes (if needed)
│
├── components/
│   ├── ui/                    # shadcn components
│   ├── chess/
│   │   ├── Board.tsx         # ~100 lines
│   │   ├── MoveList.tsx      # ~80 lines
│   │   ├── EvalBar.tsx       # ~50 lines
│   │   └── PositionCard.tsx  # ~60 lines
│   ├── identity/
│   │   ├── IdentityCard.tsx  # ~100 lines
│   │   ├── ArchetypeBadge.tsx
│   │   ├── TraitChip.tsx
│   │   └── EvolutionChart.tsx
│   ├── coach/
│   │   ├── ChatInterface.tsx # ~150 lines
│   │   ├── SocraticQuestion.tsx
│   │   └── FeedbackButtons.tsx
│   └── social/
│       ├── ShareCard.tsx
│       ├── Leaderboard.tsx
│       └── ChallengeCard.tsx
│
├── hooks/
│   ├── useIdentity.ts
│   ├── useCoach.ts
│   ├── useAnalysis.ts
│   └── useShare.ts
│
├── lib/
│   ├── api.ts                # API client
│   ├── chess.ts              # Chess utilities
│   └── analytics.ts          # Event tracking
│
└── styles/
    └── globals.css
```

### 8.2 Key Component: Identity Card (Shareable)

```tsx
// components/identity/ShareableCard.tsx

import { motion } from 'framer-motion';
import html2canvas from 'html2canvas';

interface ShareableCardProps {
  identity: Identity;
  onShare: (platform: string) => void;
}

export function ShareableCard({ identity, onShare }: ShareableCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  
  const downloadAsImage = async () => {
    if (!cardRef.current) return;
    const canvas = await html2canvas(cardRef.current);
    const link = document.createElement('a');
    link.download = `chess-identity-${identity.username}.png`;
    link.href = canvas.toDataURL();
    link.click();
  };
  
  const shareToTwitter = () => {
    const text = `I'm "${identity.archetype}" in chess! 🎯\n\nMy strengths: ${identity.traits.join(', ')}\nMy kryptonite: ${identity.weakness}\n\nDiscover your Chess Identity:`;
    const url = `https://chesscoach.ai/identity/${identity.userId}`;
    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`);
  };
  
  return (
    <div className="space-y-4">
      {/* The Card */}
      <motion.div 
        ref={cardRef}
        className="w-[400px] bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-6 text-white"
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
      >
        {/* Archetype Header */}
        <div className="text-center mb-4">
          <div className="text-4xl mb-2">{ARCHETYPE_ICONS[identity.archetype]}</div>
          <h2 className="text-2xl font-bold">{identity.archetype}</h2>
          <p className="text-slate-400">@{identity.username} • {identity.rating}</p>
        </div>
        
        {/* Stats Bars */}
        <div className="space-y-2 mb-4">
          {Object.entries(identity.metrics).map(([key, value]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="w-24 text-sm text-slate-400">{formatMetricName(key)}</span>
              <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                <motion.div 
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-500"
                  initial={{ width: 0 }}
                  animate={{ width: `${value * 100}%` }}
                  transition={{ delay: 0.2, duration: 0.5 }}
                />
              </div>
              <span className="w-12 text-sm text-right">{Math.round(value * 100)}%</span>
            </div>
          ))}
        </div>
        
        {/* Traits */}
        <div className="flex flex-wrap gap-2 mb-4">
          {identity.traits.map(trait => (
            <span key={trait} className="px-3 py-1 bg-slate-700/50 rounded-full text-sm">
              {TRAIT_ICONS[trait]} {trait}
            </span>
          ))}
        </div>
        
        {/* Weakness */}
        <div className="text-center text-sm text-amber-400 mb-4">
          ⚠️ Kryptonite: {identity.weakness}
        </div>
        
        {/* Tagline */}
        <p className="text-center text-slate-300 italic text-sm">
          "{identity.tagline}"
        </p>
        
        {/* Branding */}
        <div className="text-center text-xs text-slate-500 mt-4 pt-4 border-t border-slate-700">
          Discover your Chess Identity at chesscoach.ai
        </div>
      </motion.div>
      
      {/* Share Buttons */}
      <div className="flex justify-center gap-2">
        <Button variant="outline" onClick={shareToTwitter}>
          <Twitter className="w-4 h-4 mr-2" /> Twitter
        </Button>
        <Button variant="outline" onClick={() => onShare('reddit')}>
          Reddit
        </Button>
        <Button variant="outline" onClick={() => onShare('discord')}>
          Discord
        </Button>
        <Button variant="outline" onClick={downloadAsImage}>
          <Download className="w-4 h-4 mr-2" /> PNG
        </Button>
      </div>
    </div>
  );
}
```

---

## 9. MIGRATION PATH

### Phase 1: Foundation (Week 1-2)
```
□ Consolidate database collections (65 → 12)
□ Set up Qdrant for vector storage
□ Create new service structure
□ Set up ML training pipeline infrastructure
```

### Phase 2: ML Model (Week 3-4)
```
□ Prepare training dataset from Lichess
□ Train initial mistake classifier
□ Deploy model with A/B testing capability
□ Implement feedback → retraining pipeline
```

### Phase 3: Identity Engine (Week 5-6)
```
□ Implement new archetype system (12 archetypes)
□ Add detailed metrics tracking
□ Build narrative generator
□ Create shareable identity cards
```

### Phase 4: Viral Features (Week 7-8)
```
□ Implement share card generation
□ Add Twitter/Reddit/Discord sharing
□ Build leaderboards
□ Create challenge system
□ Implement weekly digest emails
```

### Phase 5: Coach Brain (Week 9-10)
```
□ Implement RAG with chess knowledge base
□ Add persistent user memory
□ Build Socratic questioning engine
□ Integrate all components
```

### Phase 6: Frontend Rebuild (Week 11-12)
```
□ Migrate to Next.js 14 app router
□ Component extraction from mega-files
□ Implement new identity UI
□ Add social features UI
```

---

## 10. SUCCESS METRICS

### Product Metrics
| Metric | Current | Target |
|--------|---------|--------|
| Pattern match accuracy | 0.08% | 75%+ |
| Identity card shares/week | 0 | 500+ |
| Weekly digest open rate | N/A | 40%+ |
| User correction submissions/week | ~5 | 50+ |
| 7-day retention | Unknown | 40%+ |

### Technical Metrics
| Metric | Current | Target |
|--------|---------|--------|
| Avg API response time | Unknown | <200ms |
| ML model inference time | N/A | <100ms |
| Database collections | 65 | 12 |
| Largest file LOC | 157,910 | <500 |

---

## 11. TECH STACK SUMMARY

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14, TypeScript, Tailwind, Framer Motion, shadcn/ui |
| **Backend** | FastAPI, Python 3.11+, Pydantic v2 |
| **Database** | MongoDB Atlas (primary), Redis (cache) |
| **Vector Store** | Qdrant (self-hosted or cloud) |
| **ML Framework** | PyTorch, HuggingFace Transformers |
| **LLM** | OpenAI GPT-4o, Claude (via API) |
| **Chess Engine** | Stockfish 16 |
| **Background Jobs** | Celery + Redis |
| **Monitoring** | Sentry, Prometheus, Grafana |
| **Deployment** | Docker, Kubernetes |

---

*This architecture, fully implemented, would be a 9.5/10 system. The 0.5 gap is reserved for real-world learnings and iterations that only come from production usage.*
