import React, { useState, useEffect, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ImageBackground, ActivityIndicator, Alert, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Chess } from 'chess.js';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { ChessBoardView } from '../components/ChessBoardView';
import { VictoryCelebrationModal } from '../components/VictoryCelebrationModal';
import {
  fetchAPI,
  getCoachPlayerIdentity,
  endCoachSession,
  completeEngine2Skill,
} from '../services/api';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const OPENINGS = [
  { id: 'italian', name: 'Italian Game', desc: 'Classic 1.e4 e5 (Center Control)', fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3' },
  { id: 'ruy', name: 'Ruy Lopez', desc: 'Spanish Opening (Pressure on Knight)', fen: 'r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3' },
  { id: 'sicilian', name: 'Sicilian Defense', desc: 'Sharp 1.e4 c5 Counter-Attack', fen: 'rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2' },
  { id: 'free', name: 'Standard Free Play', desc: 'Standard Starting Board', fen: START_FEN },
];

// Helper: convert UCI move (e.g. "e2e4") -> SAN (e.g. "e4") for a given FEN
function uciToSan(fen, from, to, promotion = 'q') {
  try {
    const g = new Chess(fen);
    const result = g.move({ from, to, promotion: promotion || 'q' });
    return result ? result.san : null;
  } catch (e) {
    return null;
  }
}

const ENDGAME_FENS = {
  queen_checkmate: 'k7/8/8/8/8/8/1Q6/K7 w - - 0 1',
  rook_checkmate: 'k7/8/8/8/8/8/1R6/K7 w - - 0 1',
  opposition: '4k3/8/8/4P3/4K3/8/8/8 w - - 0 1',
  rule_of_square: '8/8/p7/k7/8/8/8/K7 w - - 0 1',
  lucena_position: '2K5/4P3/8/5r2/8/8/1r6/4k3 w - - 0 1',
  philidor_position: '4k3/1r6/8/4P3/4K3/8/8/8 w - - 0 1',
};

const COURSE_MAP = {
  // Openings
  italian: { name: 'Italian Game', fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3', desc: 'Control the center with 1.e4 e5 and target f7 weakness.' },
  italian_game: { name: 'Italian Game', fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3', desc: 'Control the center with 1.e4 e5 and target f7 weakness.' },
  ruy: { name: 'Ruy Lopez', fen: 'r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3', desc: 'Press Black\'s c6 knight to exert pressure on e5 center.' },
  ruy_lopez: { name: 'Ruy Lopez', fen: 'r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3', desc: 'Press Black\'s c6 knight to exert pressure on e5 center.' },
  sicilian: { name: 'Sicilian Defense', fen: 'rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2', desc: 'Asymmetrical 1.e4 c5 counter-attack for central dominance.' },
  sicilian_defense: { name: 'Sicilian Defense', fen: 'rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2', desc: 'Asymmetrical 1.e4 c5 counter-attack for central dominance.' },
  french_defense: { name: 'French Defense', fen: 'rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2', desc: 'Solid 1.e4 e6 structure preparing d5 strike.' },
  caro_kann: { name: 'Caro-Kann Defense', fen: 'rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2', desc: 'Pawn structure 1.e4 c6 supporting central d5.' },
  queens_gambit: { name: 'Queen\'s Gambit', fen: 'rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq c3 0 2', desc: 'Classic 1.d4 d5 2.c4 offering pawn for center control.' },
  london_system: { name: 'London System', fen: 'rnbqkbnr/ppp1pppp/8/3p4/3P1B2/8/PPP1PPPP/RN1QKBNR b KQkq - 1 2', desc: 'Solid 1.d4 2.Bf4 setup with strong pawn pyramid.' },
  fried_liver: { name: 'Fried Liver Defense', fen: 'r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4', desc: 'Defend against sharp 4.Ng5 tactics on f7.' },
  fried_liver_defense: { name: 'Fried Liver Defense', fen: 'r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4', desc: 'Defend against sharp 4.Ng5 tactics on f7.' },
  vienna_game: { name: 'Vienna Game', fen: 'rnbqkbnr/pppp1ppp/8/4p3/4P3/2N5/PPPP1PPP/R1BQKBNR b KQkq - 1 2', desc: 'Develop 2.Nc3 keeping options open for f4 attack.' },
  scandinavian: { name: 'Scandinavian Defense', fen: 'rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2', desc: 'Direct 1...d5 challenge to White\'s center.' },
  stafford_gambit: { name: 'Stafford Gambit', fen: 'r1bqkb1r/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3', desc: 'Aggressive 1.e4 e5 2.Nf3 Nf6 3.Nxe5 Nc6 piece activity.' },
  scotch_game: { name: 'Scotch Game', fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQK2R b KQkq d3 0 3', desc: 'Break open the center immediately with 3.d4.' },
  four_knights: { name: 'Four Knights Game', fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 4 4', desc: 'Balanced 4 knights development in the center.' },
  evans_gambit: { name: 'Evans Gambit', fen: 'r1bqk1nr/pppp1ppp/2n5/2b1p3/1PB1P3/5N2/P1PP1PPP/RNBQK2R b KQkq b3 0 4', desc: 'Sacrifice b-pawn for rapid central dominance.' },
  
  // Endgame & Checkmates
  queen_checkmate: { name: 'Queen & King Checkmate', fen: 'k7/8/8/8/8/8/1Q6/K7 w - - 0 1', desc: 'Corner the enemy King using Queen & King coordination.' },
  rook_checkmate: { name: 'Rook & King Checkmate', fen: 'k7/8/8/8/8/8/1R6/K7 w - - 0 1', desc: 'Box enemy King to the edge with Rook & King.' },
  rk_mate: { name: 'Rook & King Checkmate', fen: 'k7/8/8/8/8/8/1R6/K7 w - - 0 1', desc: 'Box enemy King to the edge with Rook & King.' },
  rook_endgame_principles: { name: 'Rook Endgame Principles', fen: '4k3/1r6/8/4P3/4K3/8/8/8 w - - 0 1', desc: 'Activate Rook behind passed pawns (Tarrasch rule).' },
  opposition: { name: 'King Opposition', fen: '4k3/8/8/4P3/4K3/8/8/8 w - - 0 1', desc: 'Use King opposition to push your passed pawn to promotion.' },
  rule_of_square: { name: 'Rule of the Square', fen: '8/8/p7/k7/8/8/8/K7 w - - 0 1', desc: 'Calculate if your King can enter the square of opponent\'s passed pawn.' },
  lucena_position: { name: 'Lucena Position', fen: '2K5/4P3/8/5r2/8/8/1r6/4k3 w - - 0 1', desc: 'Build the bridge with your Rook to promote your 7th rank pawn.' },
  philidor_position: { name: 'Philidor Position', fen: '4k3/1r6/8/4P3/4K3/8/8/8 w - - 0 1', desc: 'Hold 3rd rank defense then check enemy King from behind.' },

  // Concepts & Tactics
  forks: { name: 'Knight & Piece Forks', fen: 'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 1 5', desc: 'Look for tactical double attacks targeting undefended pieces.' },
  pins: { name: 'Pins & Absolute Pins', fen: 'r1bqk1nr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3', desc: 'Pin enemy pieces against their King or higher-value pieces.' },
  discovered_attack: { name: 'Discovered Attack', fen: 'r1bqk2r/pppp1ppp/2n5/4p3/1bB1P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 5 4', desc: 'Move one piece to unleash a hidden attack from behind.' },
};

const findCourseMatch = (rawKey, labelName) => {
  if (rawKey && COURSE_MAP[rawKey]) return COURSE_MAP[rawKey];
  const cleanKey = rawKey ? String(rawKey).toLowerCase().replace(/^(opening_|endgame_|concept_|mate_pattern_|lesson_)/, '') : '';
  if (cleanKey && COURSE_MAP[cleanKey]) return COURSE_MAP[cleanKey];

  const searchStr = `${rawKey || ''} ${cleanKey} ${labelName || ''}`.toLowerCase();
  
  if (searchStr.includes('fried liver')) return COURSE_MAP.fried_liver;
  if (searchStr.includes('london')) return COURSE_MAP.london_system;
  if (searchStr.includes('vienna')) return COURSE_MAP.vienna_game;
  if (searchStr.includes('scandinavian')) return COURSE_MAP.scandinavian;
  if (searchStr.includes('stafford')) return COURSE_MAP.stafford_gambit;
  if (searchStr.includes('scotch')) return COURSE_MAP.scotch_game;
  if (searchStr.includes('four knights')) return COURSE_MAP.four_knights;
  if (searchStr.includes('evans')) return COURSE_MAP.evans_gambit;
  if (searchStr.includes('french')) return COURSE_MAP.french_defense;
  if (searchStr.includes('caro')) return COURSE_MAP.caro_kann;
  if (searchStr.includes('sicilian')) return COURSE_MAP.sicilian;
  if (searchStr.includes('italian')) return COURSE_MAP.italian;
  if (searchStr.includes('ruy') || searchStr.includes('spanish')) return COURSE_MAP.ruy;
  if (searchStr.includes('queen\'s gambit') || searchStr.includes('queens gambit')) return COURSE_MAP.queens_gambit;
  if (searchStr.includes('opposition')) return COURSE_MAP.opposition;
  if (searchStr.includes('square')) return COURSE_MAP.rule_of_square;
  if (searchStr.includes('lucena')) return COURSE_MAP.lucena_position;
  if (searchStr.includes('philidor')) return COURSE_MAP.philidor_position;
  if (searchStr.includes('rook mate') || searchStr.includes('rook & king')) return COURSE_MAP.rook_checkmate;
  if (searchStr.includes('queen mate') || searchStr.includes('queen & king')) return COURSE_MAP.queen_checkmate;
  if (searchStr.includes('fork')) return COURSE_MAP.forks;
  if (searchStr.includes('pin')) return COURSE_MAP.pins;
  if (searchStr.includes('discovered')) return COURSE_MAP.discovered_attack;

  return null;
};

export default function CoachPlayScreen({ navigation, route }) {
  // Pre-game state
  const [gameStarted, setGameStarted] = useState(false);
  const [selectedColor, setSelectedColor] = useState('white');
  const [selectedDifficulty, setSelectedDifficulty] = useState('auto');
  const [gameMode, setGameMode] = useState('coach');
  const [selectedOpening, setSelectedOpening] = useState('free');
  const [sessionId, setSessionId] = useState(null);
  const [activeSkillId, setActiveSkillId] = useState(null);
  const [startError, setStartError] = useState(null);
  const [showFullStartError, setShowFullStartError] = useState(true);

  const getDifficultyRating = () => {
    switch (selectedDifficulty) {
      case 'beginner': return 800;
      case 'intermediate': return 1200;
      case 'advanced': return 1600;
      case 'master': return 2000;
      default: return null;
    }
  };

  // Active game state
  const [fen, setFen] = useState(START_FEN);
  const [serverFen, setServerFen] = useState(START_FEN);
  const [initialGameFen, setInitialGameFen] = useState(START_FEN);
  const [lastMoveSan, setLastMoveSan] = useState('Start');
  const [lastMoveSquares, setLastMoveSquares] = useState(null);
  const [moveQuality, setMoveQuality] = useState('Game Started');
  const [coachAdvice, setCoachAdvice] = useState('Welcome! Make your move to start playing.');
  const [loading, setLoading] = useState(false);
  const [moveHistory, setMoveHistory] = useState([]);
  const [isPlayerTurn, setIsPlayerTurn] = useState(true);
  const [gameOver, setGameOver] = useState(false);
  const [coachThinking, setCoachThinking] = useState(false);
  const [showVictoryModal, setShowVictoryModal] = useState(false);
  const [isBubbleMinimized, setIsBubbleMinimized] = useState(false);
  const [showNotationGuide, setShowNotationGuide] = useState(false);
  const [showHintInTurnBar, setShowHintInTurnBar] = useState(false);

  // Stats
  const [stats, setStats] = useState({ wins: 0, draws: 0, losses: 1, style: 'The Improviser' });

  // Poll ref — so we can cancel on unmount / restart
  const pollRef = useRef(null);
  const sessionIdRef = useRef(null);
  const boardViewRef = useRef(null);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => () => { if (pollRef.current) clearTimeout(pollRef.current); }, []);

  // Auto-collapse offline error banner after 10 seconds into a small sign
  useEffect(() => {
    if (startError) {
      setShowFullStartError(true);
      const timer = setTimeout(() => {
        setShowFullStartError(false);
      }, 10000);
      return () => clearTimeout(timer);
    }
  }, [startError]);

  // Reset to setup screen when navigating away / switching tabs
  useEffect(() => {
    const unsubscribe = navigation?.addListener('blur', () => {
      if (pollRef.current) clearTimeout(pollRef.current);
      setGameStarted(false);
      setGameOver(false);
    });
    return unsubscribe;
  }, [navigation]);

  // Load player identity
  useEffect(() => {
    (async () => {
      try {
        const d = await getCoachPlayerIdentity();
        if (d) setStats({ wins: d.wins || 0, draws: d.draws || 0, losses: d.losses || 1, style: d.style || 'The Improviser' });
      } catch (_) { }
    })();
  }, []);

  // Monitor navigation parameters to auto-start lessons or specific game modes
  useEffect(() => {
    if (route?.params) {
      const {
        startSkillId,
        startLabel,
        startContentRef,
        startColor,
        gameMode: pGameMode,
        mode: pMode,
        opening: pOpening,
        opening_name: pOpeningName,
        courseId
      } = route.params;

      const hasParam = startSkillId || startContentRef || courseId || pOpening || pGameMode || pMode;

      if (hasParam) {
        const rawKey = startContentRef || startSkillId || courseId || pOpening;
        const matched = findCourseMatch(rawKey, startLabel || pOpeningName || pOpening);

        const selectedMode = pGameMode || pMode || 'coach';
        const selectedColorChoice = startColor || 'white';

        if (pGameMode || pMode) setGameMode(selectedMode);
        if (startColor) setSelectedColor(selectedColorChoice);

        const config = {
          startSkillId: rawKey,
          user_color: selectedColorChoice,
          game_mode: selectedMode,
          opening_name: matched?.name || pOpeningName || pOpening || startLabel,
          starting_fen: matched?.fen || START_FEN,
          course_desc: matched?.desc
        };

        handleStartGame(config);

        navigation.setParams({
          startSkillId: null,
          startContentRef: null,
          courseId: null,
          opening: null,
          gameMode: null,
          mode: null
        });
      }
    }
  }, [route?.params]);

  // Persist updated player rating, wins, accuracy, and stats to AsyncStorage
  const updateLocalUserStats = async (outcome, accuracy = 92.5) => {
    try {
      const stored = await AsyncStorage.getItem('@user_local_stats');
      let currentStats = {
        rating: stats.rating || 1200,
        wins: stats.wins || 0,
        losses: stats.losses || 0,
        draws: stats.draws || 0,
        accuracy: 92.5,
        total_games: 0,
        style: stats.style || 'The Improviser'
      };
      if (stored) {
        try { currentStats = { ...currentStats, ...JSON.parse(stored) }; } catch (_) { }
      }

      if (outcome === 'win') {
        currentStats.rating = (currentStats.rating || 1200) + 15;
        currentStats.wins = (currentStats.wins || 0) + 1;
      } else if (outcome === 'loss') {
        currentStats.rating = Math.max(800, (currentStats.rating || 1200) - 10);
        currentStats.losses = (currentStats.losses || 0) + 1;
      } else if (outcome === 'draw') {
        currentStats.rating = (currentStats.rating || 1200) + 2;
        currentStats.draws = (currentStats.draws || 0) + 1;
      }

      currentStats.total_games = currentStats.wins + currentStats.losses + currentStats.draws;
      currentStats.accuracy = Math.round((((currentStats.accuracy || 92.5) * (currentStats.total_games - 1) + accuracy) / currentStats.total_games) * 10) / 10;

      setStats(currentStats);
      await AsyncStorage.setItem('@user_local_stats', JSON.stringify(currentStats));
      console.log('[Stats] Persisted local user stats:', currentStats);
    } catch (e) {
      console.warn('[Stats] Failed to update local stats:', e);
    }
  };

  // Translate SAN notation (e.g. "Bxg5") into plain English for beginners
  const sanToPlainEnglish = (san) => {
    if (!san || san === 'Start' || san === '—') return 'Starting position';
    if (san === 'O-O') return 'Kingside Castling (King Safety)';
    if (san === 'O-O-O') return 'Queenside Castling (King Safety)';

    let text = san;
    const isCheck = text.includes('+');
    const isCheckmate = text.includes('#');
    text = text.replace(/[+#]/g, '');

    let promotionText = '';
    if (text.includes('=')) {
      const parts = text.split('=');
      text = parts[0];
      const pCode = parts[1]?.[0]?.toUpperCase();
      const pNames = { Q: 'Queen', R: 'Rook', B: 'Bishop', N: 'Knight' };
      promotionText = ` (Promotes to ${pNames[pCode] || 'Queen'})`;
    }

    const pieceCode = text[0];
    let pieceName = 'Pawn';
    let rest = text;

    if (['K', 'Q', 'R', 'B', 'N'].includes(pieceCode)) {
      const pieceMap = { K: 'King ♚', Q: 'Queen 👑', R: 'Rook 🏰', B: 'Bishop 🐘', N: 'Knight 🐴' };
      pieceName = pieceMap[pieceCode];
      rest = text.slice(1);
    }

    const isCapture = rest.includes('x');
    const square = rest.replace('x', '').slice(-2);

    let explanation = '';
    if (isCapture) {
      explanation = `${pieceName} captures on ${square.toUpperCase()}`;
    } else {
      explanation = `${pieceName} to ${square.toUpperCase()}`;
    }

    if (promotionText) explanation += promotionText;
    if (isCheckmate) explanation += ' — CHECKMATE!';
    else if (isCheck) explanation += ' (Check!)';

    return explanation;
  };

  // Move explanation with rich emojis
  const moveExplanation = (m) => {
    if (!m) return '✨ Moving pieces into action.';
    const p = m.piece?.toUpperCase();
    if (m.flags?.includes('k') || m.flags?.includes('q')) return '🏰 Castled! King is safe, Rook is active.';
    if (m.flags?.includes('c')) return '⚔️ Captured an opponent piece!';
    if (p === 'P' && ['d4', 'e4', 'd5', 'e5'].includes(m.to)) return '♟️ Center pawn push! Controlling the middle.';
    if (p === 'P') return '♟️ Pawn push! Clearing space for your pieces.';
    if (p === 'N') return '🐴 Knight out! Heading toward an active square.';
    if (p === 'B') return '🐘 Bishop active! Aiming down an open diagonal.';
    if (p === 'R') return '🏰 Rook active on an open file!';
    if (p === 'Q') return '👑 Queen joins the battle!';
    return '🎯 Good development move!';
  };

  const nextMoveHint = (g) => {
    try {
      const isMated = typeof g.isCheckmate === 'function' ? g.isCheckmate() : (typeof g.in_checkmate === 'function' ? g.in_checkmate() : false);
      const isStale = typeof g.isStalemate === 'function' ? g.isStalemate() : (typeof g.in_stalemate === 'function' ? g.in_stalemate() : false);
      const isDrawn = typeof g.isDraw === 'function' ? g.isDraw() : (typeof g.in_draw === 'function' ? g.in_draw() : false);

      if (isMated) return '🏆 CHECKMATE! The game is over.';
      if (isStale || isDrawn) return '🤝 The game is a draw.';

      const mvs = g.moves({ verbose: true });
      if (!mvs || !mvs.length) return '🚫 No legal moves left.';

      // Look for check moves
      const checkMove = mvs.find(m => m.san && m.san.includes('+'));
      if (checkMove) return `⚡ Suggestion: Check with ${checkMove.san} (${sanToPlainEnglish(checkMove.san)})!`;

      // Look for captures
      const captureMove = mvs.find(m => m.flags?.includes('c') || m.captured);
      if (captureMove) return `⚔️ Suggestion: Capture piece with ${captureMove.san} (${sanToPlainEnglish(captureMove.san)})!`;

      // Look for castling
      const castle = mvs.find(m => m.flags?.includes('k') || m.flags?.includes('q'));
      if (castle) return `🏰 Suggestion: Castle (${castle.san}) for King safety!`;

      // Knight or Bishop developments
      const minorPiece = mvs.find(m => m.piece === 'n' || m.piece === 'b');
      if (minorPiece) return `${minorPiece.piece === 'n' ? '🐴' : '🐘'} Suggestion: Play ${minorPiece.san} (${sanToPlainEnglish(minorPiece.san)})!`;

      // Central pawn push
      const centerPawn = mvs.find(m => m.piece === 'p' && ['d4', 'e4', 'd5', 'e5'].includes(m.to));
      if (centerPawn) return `♟️ Suggestion: Push center pawn with ${centerPawn.san} (${sanToPlainEnglish(centerPawn.san)})!`;

      return `🎯 Suggestion: Play ${mvs[0].san} (${sanToPlainEnglish(mvs[0].san)}) to advance.`;
    } catch (e) {
      console.log('[CoachPlay] nextMoveHint error:', e);
      return '💡 Suggestion: Develop your Knights 🐴 and Bishops 🐘, then castle 🏰 to protect your King ♚.';
    }
  };

  const stopPoll = () => {
    if (pollRef.current) { clearTimeout(pollRef.current); pollRef.current = null; }
  };

  // =========================================================================
  // Poll /coach/play/state/{sid} for coach reply (mirrors web pollForCoachResponse)
  // =========================================================================
  const startPollForCoachMove = useCallback((sid, mode, color) => {
    let attempts = 0;
    const MAX = 30; // 30 x 2s = 60s timeout

    const poll = async () => {
      if (!sessionIdRef.current) return;
      if (sid.startsWith('local_')) {
        stopPoll();
        return;
      }
      attempts++;
      try {
        const state = await fetchAPI(`/coach/play/state/${sid}`);

        // Coach finished their move
        if (state?.session && state.session.coach_move_pending === false) {
          stopPoll();
          const newFen = state.current_fen || state.session?.current_fen || START_FEN;
          setServerFen(newFen);
          setFen(newFen);

          // Get coach's last move SAN from history
          const hist = state.session?.move_history || [];
          const coachEntry = [...hist].reverse().find(m => m.by === 'coach');
          const coachSan = coachEntry?.move || '';
          if (coachSan) setMoveHistory(prev => [...prev, coachSan]);
          setLastMoveSan(coachSan || '—');

          // Fetch coaching advice (best effort)
          let advice = '';
          let cleanUserAdvice = '';
          let coachAdviceText = '';
          if (mode === 'coach') {
            try {
              const fb = await fetchAPI('/coach/play/v5/interactive-feedback', {
                method: 'POST',
                body: JSON.stringify({ session_id: sid }),
              });
              const hasCoaching = fb?.user_move_coaching || fb?.coach_move_coaching || fb?.behavioral_coaching;
              if (hasCoaching) console.log('[InteractiveFeedback] Response:', JSON.stringify(fb));

              const rawUserAdvice = fb?.user_move_coaching?.narrative || fb?.user_move_coaching?.coaching_message || '';
              coachAdviceText = fb?.coach_move_coaching?.explanation || fb?.coach_move_coaching?.narrative || '';
              const hintText = fb?.coach_move_coaching?.hint_for_user || '';

              // Clean up redundant "User Move: xx." prefix if present
              cleanUserAdvice = rawUserAdvice.replace(/^User Move:\s*[\w\d#+=-]+\.\s*/i, '').trim();

              const parts = [];
              if (cleanUserAdvice) parts.push(`💡 Feedback on your move:\n${cleanUserAdvice}`);
              if (coachAdviceText) parts.push(`🎯 Opponent move note:\n${coachAdviceText}`);
              if (hintText) parts.push(`⭐ Hint: ${hintText}`);

              advice = parts.join('\n\n');
            } catch (err) {
              console.log('[InteractiveFeedback] Error:', err);
            }
          }

          const g = new Chess(newFen);
          const hint = nextMoveHint(g);
          if (mode === 'coach') {
            const bodyText = cleanUserAdvice ? `💡 Your move: ${cleanUserAdvice}` : (coachAdviceText ? `🎯 Note: ${coachAdviceText}` : '');
            setCoachAdvice(`♟️ Opponent played: ${coachSan} (${sanToPlainEnglish(coachSan)})${bodyText ? `\n\n${bodyText}` : ''}`);
          } else {
            setCoachAdvice(`♟️ Opponent played: ${coachSan} (${sanToPlainEnglish(coachSan)}). Your turn!`);
          }
          setMoveQuality('Your Turn');
          setIsPlayerTurn(true);
          setCoachThinking(false);

          if (g.isGameOver()) localGameOver(g, color);
          return;
        }

        // Game ended while we waited
        if (state?.game_over || state?.session?.status === 'completed') {
          stopPoll();
          const newFen = state.current_fen || state.session?.current_fen || START_FEN;
          setFen(newFen); setServerFen(newFen);
          const res = state.session?.result;
          let outcome = 'seen';
          if (res === 'loss') {
            setMoveQuality('CHECKMATED');
            setCoachAdvice('Opponent won. Tap Restart!');
            setStats(p => ({ ...p, losses: p.losses + 1 }));
            outcome = 'wrong';
          }
          else if (res === 'draw') {
            setMoveQuality('DRAW');
            setCoachAdvice('Game ended in a draw!');
            setStats(p => ({ ...p, draws: p.draws + 1 }));
            outcome = 'seen';
          }
          setGameOver(true); setCoachThinking(false);

          if (activeSkillId) {
            completeEngine2Skill(activeSkillId, outcome).catch(() => { });
          }
          return;
        }
      } catch (_) { }

      if (attempts >= MAX) {
        stopPoll(); setCoachThinking(false); setIsPlayerTurn(true);
        setCoachAdvice('Coach took too long. Your turn!');
        return;
      }
      const delay = attempts < 5 ? 800 : 2000;
      pollRef.current = setTimeout(poll, delay);
    };

    pollRef.current = setTimeout(poll, 600);
  }, []);

  const localGameOver = (g, color) => {
    let outcome = null;
    if (g.isCheckmate()) {
      const winner = g.turn() === 'w' ? 'black' : 'white';
      if (winner === color) {
        setMoveQuality('VICTORY!'); setCoachAdvice('YOU WON BY CHECKMATE!');
        setStats(p => ({ ...p, wins: p.wins + 1 }));
        setShowVictoryModal(true);
        outcome = 'correct';
      } else {
        setMoveQuality('CHECKMATED'); setCoachAdvice('Opponent won. Tap Restart!');
        setStats(p => ({ ...p, losses: p.losses + 1 }));
        outcome = 'wrong';
      }
    } else if (g.isStalemate() || g.isDraw()) {
      setMoveQuality('DRAW'); setCoachAdvice('Game drawn!');
      setStats(p => ({ ...p, draws: p.draws + 1 }));
      outcome = 'seen';
    }
    setGameOver(true); setCoachThinking(false);
    if (sessionIdRef.current) endCoachSession(sessionIdRef.current).catch(() => { });

    if (activeSkillId && outcome) {
      completeEngine2Skill(activeSkillId, outcome).catch(() => { });
    }
  };

  // =========================================================================
  // Start Game — POST /coach/play/start with CORRECT field names
  // Backend expects: user_color, game_mode, opening_name, starting_fen
  // =========================================================================
  const handleStartGame = async (overrideParams = null) => {
    stopPoll();

    let skillId = activeSkillId;
    if (overrideParams?.startSkillId) {
      skillId = overrideParams.startSkillId;
    } else if (overrideParams) {
      skillId = null;
    } else {
      if (!gameOver) {
        skillId = null;
      }
    }
    setActiveSkillId(skillId);

    // Configurable parameters based on direct selections or learn redirections
    const color = overrideParams?.user_color || selectedColor;
    const mode = overrideParams?.game_mode || gameMode;
    if (overrideParams?.game_mode) setGameMode(overrideParams.game_mode);
    if (overrideParams?.user_color) setSelectedColor(overrideParams.user_color);
    const op = overrideParams ? null : OPENINGS.find(o => o.id === selectedOpening);

    const courseKey = overrideParams?.startContentRef || overrideParams?.startSkillId;
    const matchedCourse = COURSE_MAP[courseKey] || COURSE_MAP[overrideParams?.startSkillId];

    let startFen = overrideParams?.starting_fen || matchedCourse?.fen || op?.fen || START_FEN;
    let openingName = overrideParams?.opening_name || matchedCourse?.name || (op?.id !== 'free' ? op?.name : undefined);
    let courseDesc = overrideParams?.course_desc || matchedCourse?.desc;

    setLoading(true); setGameOver(false); setIsPlayerTurn(true);
    setMoveHistory([]); setCoachThinking(false); setStartError(null);
    setShowVictoryModal(false);

    let newSid = null;
    let useFen = startFen;
    let playerFirst = true;

    try {
      const body = {
        user_color: color,
        game_mode: mode,
      };
      const diffRating = getDifficultyRating();
      if (diffRating) {
        body.user_rating = diffRating;
      }
      if (openingName) {
        body.opening_name = openingName;
      }
      if (overrideParams?.opening_key) {
        body.opening_key = overrideParams.opening_key;
      }
      if (overrideParams?.training_focus_cognitive_gap) {
        body.training_focus_cognitive_gap = overrideParams.training_focus_cognitive_gap;
      }
      if (startFen && startFen !== START_FEN) {
        body.starting_fen = startFen;
      }

      const res = await fetchAPI('/coach/play/start', { method: 'POST', body: JSON.stringify(body) });
      if (res?.session_id || res?.session?.session_id) {
        newSid = res.session_id || res.session?.session_id;
        useFen = (startFen && startFen !== START_FEN) ? startFen : (res.current_fen || startFen);
        playerFirst = res.is_player_turn !== false;
      }
    } catch (e) {
      const msg = e?.message || '';
      // 402 = daily Coach Mode limit reached — show upgrade prompt, don't fall back silently
      if (msg.includes('daily_pwc_limit') || msg.toLowerCase().includes('limit reached') || msg.toLowerCase().includes('upgrade')) {
        setLoading(false);
        Alert.alert(
          '🎓 Daily Coach Limit Reached',
          msg || 'You\'ve used your free Coach Mode sessions for today. Upgrade for unlimited coaching!',
          [{ text: 'OK', style: 'default' }]
        );
        return;
      }
      // Genuine network/server error — fall back to local session
      console.log('[CoachPlay] start fallback mode activated:', msg);
      newSid = 'local_' + Date.now();
      useFen = startFen;
    }

    setSessionId(newSid);
    sessionIdRef.current = newSid;
    setFen(useFen); setServerFen(useFen); setInitialGameFen(useFen);
    setLastMoveSan('Start'); setLastMoveSquares(null); setMoveQuality('Game Started'); setGameStarted(true);

    const g = new Chess(useFen);
    const userChar = color === 'white' ? 'w' : 'b';

    if (openingName || courseDesc) {
      const lessonTitle = openingName || 'Custom Chess Lesson';
      const detailMsg = courseDesc || 'Practice your moves and tactical principles.';
      setCoachAdvice(`🎓 LESSON: ${lessonTitle}\n💡 Goal: ${detailMsg}\n\nMake your move to practice!`);
    }

    if (!playerFirst || g.turn() !== userChar) {
      setIsPlayerTurn(false); setCoachThinking(true);
      setCoachAdvice(`Game started! Opponent is making their opening move...`);
      if (newSid && !newSid.startsWith('local_')) {
        startPollForCoachMove(newSid, mode, color);
      } else {
        // Offline / Local AI opening move when playing as Black
        setTimeout(() => {
          try {
            const ai = new Chess(useFen);
            const aiMvs = ai.moves({ verbose: true });
            if (aiMvs.length > 0) {
              const pref = aiMvs.find(m => (m.from === 'e2' && m.to === 'e4') || (m.from === 'd2' && m.to === 'd4')) || aiMvs[Math.floor(Math.random() * aiMvs.length)];
              ai.move(pref);
              const aiFen = ai.fen();
              setFen(aiFen); setServerFen(aiFen);
              setLastMoveSan(pref.san); setLastMoveSquares({ from: pref.from, to: pref.to });
              const initHist = [pref.san];
              setMoveHistory(initHist);
              AsyncStorage.setItem('@last_played_game', JSON.stringify({
                date: new Date().toISOString(),
                game_mode: mode,
                player_color: color,
                starting_fen: START_FEN,
                moves: initHist,
                accuracy: 92.5
              })).catch(() => { });
              const hint = nextMoveHint(ai);
              setCoachAdvice(
                mode === 'coach'
                  ? `Opponent played: ${pref.san}. Playing as ${color.toUpperCase()} — ${openingName || 'Standard'}.\n\n${hint}`
                  : `Opponent played: ${pref.san}. Your turn!`
              );
              setMoveQuality('Your Turn');
            }
          } catch (e) {
            console.log('[CoachPlay] local opening move error:', e);
          }
          setCoachThinking(false);
          setIsPlayerTurn(true);
        }, 600);
      }
    } else {
      setIsPlayerTurn(true);
      setCoachAdvice(
        mode === 'coach'
          ? `Coach Mode! Playing as ${color.toUpperCase()} — ${openingName || 'Custom Lesson'}. Make your move!`
          : `Play Mode! You are ${color.toUpperCase()}. Good luck!`
      );
    }
    setLoading(false);
  };

  // =========================================================================
  // User makes a move on the board
  // =========================================================================
  const handleUserMove = async (moveData) => {
    if (!moveData?.from || !moveData?.to) return;
    if (!isPlayerTurn || coachThinking || gameOver) return;

    let promo = moveData?.promotion;
    if (!promo && moveData?.san && typeof moveData.san === 'string' && moveData.san.includes('=')) {
      const parts = moveData.san.split('=');
      if (parts[1]) promo = parts[1][0].toLowerCase();
    }
    if (!promo) promo = 'q';

    const curFen = serverFen || fen;

    // Convert board move to SAN (backend needs SAN, not UCI)
    const moveSan = moveData?.san || uciToSan(curFen, moveData.from, moveData.to, promo);
    if (!moveSan) { setCoachAdvice('Illegal move!'); return; }

    // Apply locally for instant feedback
    let g;
    try { g = new Chess(curFen); } catch (_) { g = new Chess(START_FEN); }
    const moveResult = g.move({ from: moveData.from, to: moveData.to, promotion: promo });
    if (!moveResult) { setCoachAdvice('Illegal move!'); return; }

    const userFen = g.fen();
    setFen(userFen);
    setLastMoveSan(moveSan); setLastMoveSquares({ from: moveData.from, to: moveData.to });
    const newHist = [...moveHistory, moveSan];
    setMoveHistory(newHist);
    try {
      AsyncStorage.setItem('@last_played_game', JSON.stringify({
        date: new Date().toISOString(),
        game_mode: gameMode,
        player_color: selectedColor,
        starting_fen: initialGameFen || START_FEN,
        moves: newHist,
        accuracy: 92.5
      })).catch(() => { });
    } catch (_) { }
    const exp = moveExplanation(moveResult);

    // Check local game-over (checkmate/stalemate by user's move)
    if (g.isCheckmate()) {
      setMoveQuality('CHECKMATE!');
      setCoachAdvice(`YOU WON BY CHECKMATE WITH ${moveSan}!`);
      updateLocalUserStats('win');
      setGameOver(true);
      setShowVictoryModal(true);
      if (sessionId) endCoachSession(sessionId).catch(() => { });
      if (activeSkillId) completeEngine2Skill(activeSkillId, 'correct').catch(() => { });
      return;
    }
    if (g.isStalemate() || g.isDraw()) {
      setMoveQuality('STALEMATE'); setCoachAdvice('Game drawn by stalemate!');
      updateLocalUserStats('draw');
      setGameOver(true);
      if (sessionId) endCoachSession(sessionId).catch(() => { });
      if (activeSkillId) completeEngine2Skill(activeSkillId, 'seen').catch(() => { });
      return;
    }

    // Show "coach thinking" state
    setIsPlayerTurn(false); setCoachThinking(true);
    setMoveQuality('Coach Thinking...');
    setCoachAdvice(`You played ${moveSan}: ${exp}\nCoach is thinking...`);

    // POST /coach/play/move — only session_id, move (SAN), thinking_time_ms
    if (sessionId && !sessionId.startsWith('local_')) {
      try {
        const res = await fetchAPI('/coach/play/move', {
          method: 'POST',
          body: JSON.stringify({ session_id: sessionId, move: moveSan, thinking_time_ms: 0 }),
        });
        if (res?.game_over) {
          stopPoll();
          const r = res.result;
          let outcome = 'seen';
          if (r === 'win') {
            setMoveQuality('CHECKMATE!');
            setCoachAdvice(`You won! ${moveSan} was checkmate!`);
            setStats(p => ({ ...p, wins: p.wins + 1 }));
            setShowVictoryModal(true);
            outcome = 'correct';
          }
          else if (r === 'draw') {
            setMoveQuality('DRAW');
            setCoachAdvice('Game ended in a draw!');
            setStats(p => ({ ...p, draws: p.draws + 1 }));
            outcome = 'seen';
          }
          setGameOver(true); setCoachThinking(false);
          if (sessionId) endCoachSession(sessionId).catch(() => { });
          if (activeSkillId) completeEngine2Skill(activeSkillId, outcome).catch(() => { });
          return;
        }
        if (res?.current_fen) { setServerFen(res.current_fen); setFen(res.current_fen); }
        if (res?.awaiting_coach) {
          startPollForCoachMove(sessionId, gameMode, selectedColor);
          return;
        }
      } catch (e) {
        console.log('[CoachPlay] /move failed:', e?.message);
      }
    }

    // Local AI fallback
    setTimeout(() => {
      try {
        const ai = new Chess(userFen);
        const aiMvs = ai.moves({ verbose: true });
        if (!aiMvs.length) { setCoachThinking(false); setIsPlayerTurn(true); return; }
        const pick = aiMvs[Math.floor(Math.random() * aiMvs.length)];
        ai.move(pick);
        const aiFen = ai.fen();
        setFen(aiFen); setServerFen(aiFen);
        setLastMoveSan(pick.san); setLastMoveSquares({ from: pick.from, to: pick.to });
        const newHist = [...moveHistory, moveSan, pick.san];
        setMoveHistory(newHist);
        try {
          AsyncStorage.setItem('@last_played_game', JSON.stringify({
            date: new Date().toISOString(),
            game_mode: gameMode,
            player_color: selectedColor,
            starting_fen: initialGameFen || START_FEN,
            moves: newHist,
            accuracy: 92.5
          })).catch(() => { });
        } catch (_) { }
        if (ai.isCheckmate()) { localGameOver(ai, selectedColor); return; }
        const hint = nextMoveHint(ai);
        setCoachAdvice(
          gameMode === 'coach'
            ? `♟️ Opponent played: ${pick.san} (${sanToPlainEnglish(pick.san)})\n\n💡 Your move (${moveSan} - ${sanToPlainEnglish(moveSan)}): ${exp}`
            : `♟️ Opponent played: ${pick.san} (${sanToPlainEnglish(pick.san)}). Your turn!`
        );
        setMoveQuality('Your Turn');
        setCoachThinking(false); setIsPlayerTurn(true);
      } catch (_) { setCoachThinking(false); setIsPlayerTurn(true); }
    }, 600);
  };

  const handleNoMoves = (sq) => setCoachAdvice(`Piece on ${sq?.toUpperCase() || 'that square'} cannot move!`);

  const handleGameOver = (data) => {
    if (data?.reason === 'CHECKMATE') {
      const w = (data?.winner || 'White').toLowerCase();
      if (w === selectedColor) {
        setMoveQuality('VICTORY!'); setCoachAdvice('YOU WON BY CHECKMATE!');
        updateLocalUserStats('win');
        setShowVictoryModal(true);
      } else {
        setMoveQuality('CHECKMATED'); setCoachAdvice('Opponent won.');
        updateLocalUserStats('loss');
      }
      setGameOver(true);
    }
  };

  // =========================================================================
  // Render
  // =========================================================================
  return (
    <ImageBackground source={require('../../assets/dashboard_chess_bg.png')} style={st.bg} resizeMode="cover">
      <View style={st.overlay} />
      <SafeAreaView style={st.safe}>
        {!gameStarted ? (
          /* ── SETUP: scrollable ── */
          <ScrollView style={st.scroll} contentContainerStyle={st.content} showsVerticalScrollIndicator={false}>
            <View style={st.setupCard}>
              <View style={st.headerRow}>
                <View style={st.iconCircle}><Text style={st.iconTxt}>⚔️</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={st.setupTitle}>Play With Coach</Text>
                  <Text style={st.setupSub}>Train against an intelligent AI opponent</Text>
                </View>
              </View>

              {startError && (
                <View style={st.errCard}>
                  <Text style={st.errTitle}>⚠️ Play Limit Reached</Text>
                  <Text style={st.errText}>{startError}</Text>
                  <Text style={st.errSubtext}>You will be playing in offline fallback mode.</Text>
                </View>
              )}

              <Text style={st.label}>Choose Your Color</Text>
              <View style={st.row}>
                {['white', 'black'].map(c => (
                  <TouchableOpacity key={c} style={[st.colorBtn, selectedColor === c && st.colorBtnOn]} onPress={() => setSelectedColor(c)}>
                    <Text style={st.colorDot}>{c === 'white' ? '⚪' : '🖤'}</Text>
                    <Text style={[st.colorTxt, selectedColor === c && st.colorTxtOn]}>{c === 'white' ? 'White' : 'Black'}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={st.label}>Opponent Difficulty</Text>
              <View style={st.diffGrid}>
                {[
                  { id: 'auto', label: 'Adaptive 🤖', sub: 'Matches ELO' },
                  { id: 'beginner', label: 'Beginner 👶', sub: '800 ELO' },
                  { id: 'intermediate', label: 'Medium ♟️', sub: '1200 ELO' },
                  { id: 'advanced', label: 'Expert 🔥', sub: '1600 ELO' },
                  { id: 'master', label: 'Master 🏆', sub: '2000 ELO' },
                ].map(d => (
                  <TouchableOpacity
                    key={d.id}
                    style={[st.diffBtn, selectedDifficulty === d.id && st.diffBtnOn]}
                    onPress={() => setSelectedDifficulty(d.id)}
                  >
                    <Text style={[st.diffBtnTxt, selectedDifficulty === d.id && st.diffBtnTxtOn]}>{d.label}</Text>
                    <Text style={st.diffBtnSub}>{d.sub}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={st.label}>Game Type</Text>
              <View style={st.row}>
                {[
                  { id: 'coach', icon: '🧠', title: 'Coach Mode', sub: 'Real-time teaching & feedback', rec: true },
                  { id: 'play', icon: '♟️', title: 'Play Mode', sub: 'Pure chess, no hints' },
                ].map(m => (
                  <TouchableOpacity key={m.id} style={[st.modeCard, gameMode === m.id && st.modeCardOn]} onPress={() => setGameMode(m.id)}>
                    {m.rec && gameMode === m.id && <View style={st.recTag}><Text style={st.recTxt}>RECOMMENDED</Text></View>}
                    <Text style={st.modeIcon}>{m.icon}</Text>
                    <Text style={st.modeTitle}>{m.title}</Text>
                    <Text style={st.modeSub}>{m.sub}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <View style={st.statsCard}>
                <Text style={st.statsTitle}>📜 Coach Remembers</Text>
                <View style={st.statsRow}>
                  {[['Wins', stats.wins, '#22c55e'], ['Draws', stats.draws, '#cbd5e1'], ['Losses', stats.losses, '#ef4444']].map(([l, v, c]) => (
                    <View key={l} style={st.statBox}>
                      <Text style={[st.statVal, { color: c }]}>{v}</Text>
                      <Text style={st.statLbl}>{l}</Text>
                    </View>
                  ))}
                </View>
                <View style={st.badgeRow}>
                  <Text style={st.badgeLbl}>Your style:</Text>
                  <View style={st.badge}><Text style={st.badgeTxt}>✨ {stats.style}</Text></View>
                </View>
              </View>

              <Text style={st.label}>Pick an opening to practice</Text>
              <View style={st.openingGrid}>
                {OPENINGS.map(op => (
                  <TouchableOpacity key={op.id} style={[st.chip, selectedOpening === op.id && st.chipOn]} onPress={() => setSelectedOpening(op.id)}>
                    <View style={{ flex: 1 }}>
                      <Text style={[st.chipTxt, selectedOpening === op.id && st.chipTxtOn]}>{op.name}</Text>
                      <Text style={st.chipSub}>{op.desc}</Text>
                    </View>
                    {selectedOpening === op.id && <Text style={st.checkMark}>✓</Text>}
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity style={st.startBtn} onPress={handleStartGame} disabled={loading}>
                {loading ? <ActivityIndicator size="small" color="#090d16" /> : <Text style={st.startBtnTxt}>▶️  Start Game</Text>}
              </TouchableOpacity>
            </View>
          </ScrollView>

        ) : (
          /* ── ACTIVE GAME: fixed full-screen, NO ScrollView ── */
          <View style={st.gameScreen}>
            {/* Top Row: Left-aligned Offline Warning + Right-aligned Settings Button */}
            <View style={st.topHeaderRow}>
              {startError ? (
                <TouchableOpacity
                  style={st.leftOfflineBadge}
                  onPress={() => setShowFullStartError(!showFullStartError)}
                  activeOpacity={0.8}
                >
                  <Text style={st.leftOfflineText}>⚠️ Offline Mode</Text>
                </TouchableOpacity>
              ) : (
                <View style={{ flex: 1 }} />
              )}

              <TouchableOpacity
                style={st.topSettingsBtn}
                onPress={() => boardViewRef.current?.openSettings?.()}
                activeOpacity={0.8}
              >
                <Text style={st.topSettingsBtnText}>⚙️ Settings</Text>
              </TouchableOpacity>
            </View>

            {startError && showFullStartError && (
              <TouchableOpacity
                style={[st.errCard, { marginBottom: 8, marginTop: 4 }]}
                onPress={() => setShowFullStartError(false)}
                activeOpacity={0.9}
              >
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={st.errTitle}>⚠️ Offline Fallback Active</Text>
                  <Text style={{ color: '#94a3b8', fontSize: 11, fontWeight: '700' }}>Tap to minimize</Text>
                </View>
                <Text style={st.errText}>{startError}</Text>
              </TouchableOpacity>
            )}

            {/* Premium Glassmorphic Coach Speech Bubble */}
            {gameMode === 'coach' && (
              isBubbleMinimized ? (
                <TouchableOpacity
                  style={st.minimizedBubbleBadge}
                  onPress={() => setIsBubbleMinimized(false)}
                  activeOpacity={0.85}
                >
                  <View style={st.minimizedBubbleRow}>
                    <View style={st.glowingDot} />
                    <Text style={st.minimizedBubbleText}>🧙‍♂️ AI Coach Advice available</Text>
                    <Text style={st.minimizedExpandText}>Tap to expand ▾</Text>
                  </View>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={st.bubbleCardContainer}
                  onPress={() => setIsBubbleMinimized(true)}
                  activeOpacity={0.96}
                >
                  <View style={st.bubbleCardHeader}>
                    <View style={st.coachHeaderBadge}>
                      <Text style={st.coachHeaderBadgeIcon}>🧙‍♂️</Text>
                      <Text style={st.coachHeaderBadgeText}>AI COACH GURU</Text>
                    </View>
                    <View style={st.minimizeBtnPill}>
                      <Text style={st.minimizeBtnPillText}>Minimize ▴</Text>
                    </View>
                  </View>

                  {coachThinking ? (
                    <View style={st.thinkingContainer}>
                      <ActivityIndicator size="small" color="#eab308" />
                      <Text style={st.thinkingText}>Coach is analyzing board position...</Text>
                    </View>
                  ) : (
                    <ScrollView style={{ maxHeight: 110 }} nestedScrollEnabled showsVerticalScrollIndicator={true}>
                      <Text style={st.bubbleTxt}>{coachAdvice}</Text>
                    </ScrollView>
                  )}
                </TouchableOpacity>
              )
            )}

            {/* Chess board — centered, takes available space */}
            <View style={st.board}>
              <ChessBoardView
                ref={boardViewRef}
                fen={fen}
                orientation={selectedColor}
                lastMove={lastMoveSquares}
                onMove={handleUserMove}
                onNoMoves={handleNoMoves}
                onGameOver={handleGameOver}
                showControls={false}
              />
            </View>

            {/* Premium 2-Row Turn & Stockfish Suggestion Card */}
            {!gameOver && (
              <TouchableOpacity
                style={[
                  st.turnSuggestionCard,
                  {
                    borderColor: showHintInTurnBar
                      ? '#eab308'
                      : (isPlayerTurn ? 'rgba(34, 197, 94, 0.6)' : 'rgba(234, 179, 8, 0.6)')
                  }
                ]}
                onPress={() => setShowHintInTurnBar(prev => !prev)}
                activeOpacity={0.9}
              >
                <View style={st.turnCardHeaderRow}>
                  <View style={[st.turnStatusBadge, { backgroundColor: isPlayerTurn ? 'rgba(34, 197, 94, 0.2)' : 'rgba(234, 179, 8, 0.2)' }]}>
                    <View style={[st.statusPulseDot, { backgroundColor: isPlayerTurn ? '#22c55e' : '#eab308' }]} />
                    <Text style={[st.turnStatusText, { color: isPlayerTurn ? '#4ade80' : '#fef08a' }]}>
                      {isPlayerTurn ? 'YOUR TURN' : 'COACH THINKING'}
                    </Text>
                  </View>
                  {isPlayerTurn && (
                    <View style={[st.hintTagBadge, showHintInTurnBar && { backgroundColor: 'rgba(234, 179, 8, 0.25)' }]}>
                      <Text style={[st.hintTagText, showHintInTurnBar && { color: '#fef08a', fontWeight: '900' }]}>
                        {showHintInTurnBar ? '💡 Hint Active' : '💡 Move Hint'}
                      </Text>
                    </View>
                  )}
                </View>

                <View style={st.turnCardBodyRow}>
                  <Text style={st.turnSuggestionText}>
                    {isPlayerTurn
                      ? (showHintInTurnBar ? nextMoveHint(new Chess(fen)) : '✨ Make your move or tap 💡 Hint for advice')
                      : '⏳ Opponent is calculating countermove...'}
                  </Text>
                </View>
              </TouchableOpacity>
            )}

            {/* Action buttons */}
            <View style={st.controls}>
              {gameMode === 'coach' && isPlayerTurn && !gameOver && (
                <TouchableOpacity
                  style={[st.hintBtn, showHintInTurnBar && { backgroundColor: '#fef08a' }]}
                  onPress={() => setShowHintInTurnBar(prev => !prev)}
                >
                  <Text style={st.hintBtnTxt}>💡 Hint</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={st.restartBtn} onPress={handleStartGame}>
                <Text style={st.restartBtnTxt}>🔄 Restart</Text>
              </TouchableOpacity>
            </View>

            {/* AI Coach Status indicator card at the bottom */}
            <View style={st.bottomCoachCard}>
              <Text style={st.bottomCoachText}>
                🧙‍♂️ Coach Guru • {gameMode === 'coach' ? 'Coach Mode' : 'Play Mode'}{coachThinking ? ' (Thinking...)' : ''}
              </Text>
            </View>
          </View>
        )}

        {/* Victory Party Popper Celebration Modal */}
        <VictoryCelebrationModal
          visible={showVictoryModal}
          winningMove={lastMoveSan}
          totalMoves={moveHistory.length}
          onPlayAgain={() => {
            setShowVictoryModal(false);
            handleStartGame();
          }}
          onClose={() => setShowVictoryModal(false)}
        />

        {/* Interactive Chess Notation Guide Modal */}
        <Modal
          visible={showNotationGuide}
          animationType="slide"
          transparent={true}
          onRequestClose={() => setShowNotationGuide(false)}
        >
          <View style={st.guideModalOverlay}>
            <View style={st.guideModalContent}>
              <View style={st.guideHeader}>
                <Text style={st.guideTitle}>📖 Chess Notation Guide</Text>
                <TouchableOpacity style={st.guideCloseBtn} onPress={() => setShowNotationGuide(false)}>
                  <Text style={{ color: '#fff', fontWeight: '800' }}>✕</Text>
                </TouchableOpacity>
              </View>

              <ScrollView style={{ maxHeight: 380 }} showsVerticalScrollIndicator={true}>
                <Text style={st.guideSectionHeading}>Piece Letters:</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#eab308', fontWeight: '800' }}>B</Text> = Bishop 🐘 (e.g. <Text style={{ color: '#38bdf8' }}>Bxg5</Text> = Bishop captures on g5)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#eab308', fontWeight: '800' }}>N</Text> = Knight 🐴 (e.g. <Text style={{ color: '#38bdf8' }}>Nf3</Text> = Knight moves to f3)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#eab308', fontWeight: '800' }}>R</Text> = Rook / Elephant 🏰 (e.g. <Text style={{ color: '#38bdf8' }}>Re1</Text> = Rook to e1)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#eab308', fontWeight: '800' }}>Q</Text> = Queen 👑 (e.g. <Text style={{ color: '#38bdf8' }}>Qxd4</Text> = Queen captures on d4)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#eab308', fontWeight: '800' }}>K</Text> = King ♚ (e.g. <Text style={{ color: '#38bdf8' }}>Kg1</Text> = King to g1)</Text>
                <Text style={st.guideItem}>• No Letter (e.g. <Text style={{ color: '#38bdf8' }}>e4</Text>) = Pawn move to e4</Text>

                <Text style={[st.guideSectionHeading, { marginTop: 14 }]}>Action Symbols:</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#ef4444', fontWeight: '800' }}>x</Text> = Captures / Kills piece (e.g. <Text style={{ color: '#38bdf8' }}>Bxg5</Text>)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#eab308', fontWeight: '800' }}>+</Text> = Check (Opponent King under attack)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#22c55e', fontWeight: '800' }}>#</Text> = Checkmate (Game Won! 🎉)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#38bdf8', fontWeight: '800' }}>O-O</Text> = Kingside Castling (King Safety)</Text>
                <Text style={st.guideItem}>• <Text style={{ color: '#eab308', fontWeight: '800' }}>=Q</Text> = Pawn Promotion to Queen</Text>
              </ScrollView>

              <TouchableOpacity style={st.guideDoneBtn} onPress={() => setShowNotationGuide(false)}>
                <Text style={st.guideDoneBtnText}>Got it!</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </ImageBackground>
  );
}

const st = StyleSheet.create({
  bg: { flex: 1, width: '100%', height: '100%' },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(5,8,16,0.45)' },
  safe: { flex: 1 },
  scroll: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },

  // Active game — fixed full screen, no scrolling
  gameScreen: { flex: 1, paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, justifyContent: 'space-between' },

  // Setup
  setupCard: { backgroundColor: 'rgba(15,23,42,0.94)', borderRadius: 26, padding: 22, borderWidth: 1.5, borderColor: 'rgba(234,179,8,0.4)', elevation: 12 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 20 },
  iconCircle: { width: 52, height: 52, borderRadius: 26, backgroundColor: 'rgba(234,179,8,0.2)', justifyContent: 'center', alignItems: 'center', borderWidth: 1.5, borderColor: '#eab308' },
  iconTxt: { fontSize: 26 },
  setupTitle: { color: '#fff', fontSize: 24, fontWeight: '900' },
  setupSub: { color: '#cbd5e1', fontSize: 13, marginTop: 2 },
  label: { color: '#fff', fontSize: 14, fontWeight: '800', marginTop: 16, marginBottom: 10 },
  row: { flexDirection: 'row', gap: 12, marginBottom: 14 },

  colorBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: 'rgba(30,41,59,0.85)', borderRadius: 18, paddingVertical: 14, borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.18)' },
  colorBtnOn: { backgroundColor: 'rgba(234,179,8,0.25)', borderColor: '#eab308' },
  colorDot: { fontSize: 18 },
  colorTxt: { color: '#cbd5e1', fontWeight: '800', fontSize: 15 },
  colorTxtOn: { color: '#fef08a', fontWeight: '900' },

  modeCard: { flex: 1, backgroundColor: 'rgba(30,41,59,0.85)', borderRadius: 20, padding: 16, borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.18)', alignItems: 'center', position: 'relative' },
  modeCardOn: { backgroundColor: 'rgba(234,179,8,0.25)', borderColor: '#eab308' },
  recTag: { position: 'absolute', top: -10, backgroundColor: '#eab308', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  recTxt: { color: '#000', fontSize: 9, fontWeight: '900' },
  modeIcon: { fontSize: 26, marginBottom: 6, marginTop: 4 },
  modeTitle: { color: '#fff', fontWeight: '900', fontSize: 15, marginBottom: 3 },
  modeSub: { color: '#cbd5e1', fontSize: 11, textAlign: 'center' },

  statsCard: { backgroundColor: 'rgba(30,41,59,0.65)', borderRadius: 20, padding: 16, borderWidth: 1, borderColor: 'rgba(255,255,255,0.2)', marginVertical: 12 },
  statsTitle: { color: '#fff', fontWeight: '800', fontSize: 14, marginBottom: 12 },
  statsRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 12 },
  statBox: { alignItems: 'center' },
  statVal: { fontSize: 22, fontWeight: '900' },
  statLbl: { color: '#94a3b8', fontSize: 12, fontWeight: '700' },
  badgeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  badgeLbl: { color: '#cbd5e1', fontSize: 12 },
  badge: { backgroundColor: 'rgba(234,179,8,0.25)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10, borderWidth: 1, borderColor: '#eab308' },
  badgeTxt: { color: '#fef08a', fontWeight: '800', fontSize: 12 },

  diffGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 },
  diffBtn: { flex: 1, minWidth: '28%', backgroundColor: 'rgba(30,41,59,0.85)', borderRadius: 14, paddingVertical: 10, paddingHorizontal: 6, alignItems: 'center', borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.18)' },
  diffBtnOn: { backgroundColor: 'rgba(234,179,8,0.25)', borderColor: '#eab308' },
  diffBtnTxt: { color: '#cbd5e1', fontWeight: '800', fontSize: 13 },
  diffBtnTxtOn: { color: '#fef08a', fontWeight: '900' },
  diffBtnSub: { color: '#94a3b8', fontSize: 9, marginTop: 2 },

  openingGrid: { gap: 10, marginBottom: 24 },
  chip: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: 'rgba(30,41,59,0.85)', borderRadius: 16, paddingVertical: 14, paddingHorizontal: 16, borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.18)' },
  chipOn: { backgroundColor: 'rgba(234,179,8,0.25)', borderColor: '#eab308' },
  chipTxt: { color: '#cbd5e1', fontWeight: '800', fontSize: 14 },
  chipTxtOn: { color: '#fef08a', fontWeight: '900' },
  chipSub: { color: '#94a3b8', fontSize: 11, marginTop: 2 },
  checkMark: { color: '#eab308', fontWeight: '900', fontSize: 18 },

  startBtn: { backgroundColor: '#eab308', borderRadius: 20, paddingVertical: 18, alignItems: 'center', elevation: 8 },
  startBtnTxt: { color: '#090d16', fontWeight: '900', fontSize: 18 },

  // Active game bottom coach status
  bottomCoachCard: { backgroundColor: 'rgba(15,23,42,0.8)', borderRadius: 12, paddingVertical: 6, paddingHorizontal: 12, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  bottomCoachText: { color: '#cbd5e1', fontSize: 11, fontWeight: '700' },

  qualityBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'rgba(15,23,42,0.85)', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1.2, borderColor: 'rgba(255,255,255,0.25)', marginBottom: 10, marginTop: 24 },
  sanBadge: { backgroundColor: 'rgba(234,179,8,0.25)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  sanTxt: { color: '#fef08a', fontWeight: '900', fontSize: 12 },
  qualityTxt: { color: '#22c55e', fontWeight: '900' },

  bubble: { backgroundColor: 'rgba(15,23,42,0.9)', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1.5, borderColor: 'rgba(234,179,8,0.6)', justifyContent: 'center' },
  bubbleTxt: { color: '#fff', fontSize: 12, fontWeight: '700', lineHeight: 17 },

  board: { alignItems: 'center' },

  turnBar: { borderRadius: 10, borderWidth: 1.5, paddingVertical: 6, paddingHorizontal: 14, alignItems: 'center', backgroundColor: 'rgba(15,23,42,0.75)' },
  turnTxt: { fontWeight: '800', fontSize: 13 },

  controls: { flexDirection: 'row', gap: 8 },
  hintBtn: { flex: 1, backgroundColor: '#eab308', borderRadius: 14, paddingVertical: 12, alignItems: 'center' },
  hintBtnTxt: { color: '#000', fontWeight: '900', fontSize: 13 },
  restartBtn: { flex: 1, backgroundColor: 'rgba(239, 68, 68, 0.1)', borderRadius: 14, paddingVertical: 12, alignItems: 'center', borderWidth: 1.2, borderColor: '#ef4444' },
  restartBtnTxt: { color: '#ef4444', fontWeight: '900', fontSize: 13 },
  setupBtn: { flex: 1, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 14, paddingVertical: 12, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.3)' },
  setupBtnTxt: { color: '#fff', fontWeight: '900', fontSize: 13 },

  logCard: { backgroundColor: 'rgba(15,23,42,0.85)', borderRadius: 16, paddingHorizontal: 14, paddingVertical: 10, borderWidth: 1, borderColor: 'rgba(255,255,255,0.2)', flexDirection: 'row', alignItems: 'center', gap: 8 },
  logTitle: { color: '#94a3b8', fontSize: 11, fontWeight: '800' },
  logTxt: { color: '#fef08a', fontSize: 12, fontWeight: '700' },

  errCard: { backgroundColor: 'rgba(239, 68, 68, 0.15)', borderRadius: 16, padding: 14, borderWidth: 1.2, borderColor: '#ef4444', marginBottom: 16 },
  errTitle: { color: '#fca5a5', fontWeight: '900', fontSize: 13, marginBottom: 4 },
  errText: { color: '#fff', fontSize: 12, fontWeight: '600', lineHeight: 17 },
  errSubtext: { color: '#94a3b8', fontSize: 10, fontWeight: '700', marginTop: 6 },

  compactOfflineBadge: {
    alignSelf: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: '#ef4444',
    borderWidth: 1,
    paddingVertical: 3,
    paddingHorizontal: 12,
    borderRadius: 12,
    marginVertical: 4,
  },
  compactOfflineText: {
    color: '#fca5a5',
    fontSize: 11,
    fontWeight: '700',
  },

  topHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
    paddingHorizontal: 2,
  },
  leftOfflineBadge: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: '#ef4444',
    borderWidth: 1,
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 10,
  },
  leftOfflineText: {
    color: '#fca5a5',
    fontSize: 11,
    fontWeight: '800',
  },
  topSettingsBtn: {
    backgroundColor: 'rgba(30, 41, 59, 0.85)',
    borderColor: 'rgba(255, 255, 255, 0.2)',
    borderWidth: 1.2,
    paddingVertical: 5,
    paddingHorizontal: 12,
    borderRadius: 10,
  },
  topSettingsBtnText: {
    color: '#fef08a',
    fontSize: 12,
    fontWeight: '800',
  },

  guideModalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.8)', justifyContent: 'flex-end' },
  guideModalContent: { backgroundColor: '#0f172a', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, borderWidth: 1, borderColor: 'rgba(255,255,255,0.15)' },
  guideHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.1)' },
  guideTitle: { fontSize: 18, fontWeight: '800', color: '#fff' },
  guideCloseBtn: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#1e293b', alignItems: 'center', justifyContent: 'center' },
  guideSectionHeading: { color: '#94a3b8', fontSize: 12, fontWeight: '800', textTransform: 'uppercase', marginBottom: 6 },
  guideItem: { color: '#cbd5e1', fontSize: 13, lineHeight: 22, marginBottom: 4 },
  guideDoneBtn: { backgroundColor: '#eab308', paddingVertical: 12, borderRadius: 12, alignItems: 'center', marginTop: 14 },
  guideDoneBtnText: { color: '#0f172a', fontWeight: '800', fontSize: 15 },

  // Minimized Coach Speech Bubble
  minimizedBubbleBadge: {
    backgroundColor: 'rgba(15, 23, 42, 0.92)',
    borderColor: 'rgba(234, 179, 8, 0.5)',
    borderWidth: 1.2,
    borderRadius: 14,
    paddingVertical: 8,
    paddingHorizontal: 14,
    marginVertical: 4,
  },
  minimizedBubbleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  glowingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#eab308',
  },
  minimizedBubbleText: {
    color: '#fef08a',
    fontSize: 12,
    fontWeight: '800',
    flex: 1,
    marginLeft: 8,
  },
  minimizedExpandText: {
    color: '#94a3b8',
    fontSize: 11,
    fontWeight: '700',
  },

  // Expanded Coach Speech Bubble Card
  bubbleCardContainer: {
    backgroundColor: 'rgba(15, 23, 42, 0.94)',
    borderRadius: 18,
    padding: 12,
    borderWidth: 1.5,
    borderColor: 'rgba(234, 179, 8, 0.5)',
    shadowColor: '#eab308',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 8,
    marginVertical: 4,
  },
  bubbleCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.08)',
  },
  coachHeaderBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(234, 179, 8, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(234, 179, 8, 0.3)',
  },
  coachHeaderBadgeIcon: {
    fontSize: 12,
  },
  coachHeaderBadgeText: {
    color: '#fef08a',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  minimizeBtnPill: {
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  minimizeBtnPillText: {
    color: '#94a3b8',
    fontSize: 10,
    fontWeight: '700',
  },
  thinkingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
  },
  thinkingText: {
    color: '#cbd5e1',
    fontSize: 12,
    fontWeight: '700',
  },

  // Turn & Best Move Suggestion Card
  turnSuggestionCard: {
    backgroundColor: 'rgba(15, 23, 42, 0.92)',
    borderRadius: 16,
    padding: 12,
    borderWidth: 1.5,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 6,
    marginVertical: 4,
  },
  turnCardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  turnStatusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  statusPulseDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  turnStatusText: {
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 0.6,
  },
  hintTagBadge: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
  },
  hintTagText: {
    color: '#94a3b8',
    fontSize: 10,
    fontWeight: '700',
  },
  turnCardBodyRow: {
    marginTop: 2,
  },
  turnSuggestionText: {
    color: '#f0fdf4',
    fontSize: 13,
    fontWeight: '800',
    lineHeight: 18,
  },
});
