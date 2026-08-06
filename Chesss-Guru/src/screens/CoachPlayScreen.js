import React, { useState, useEffect, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ImageBackground, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Chess } from 'chess.js';
import { ChessBoardView } from '../components/ChessBoardView';
import {
  fetchAPI,
  getCoachPlayerIdentity,
  endCoachSession,
} from '../services/api';

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

const OPENINGS = [
  { id: 'italian',  name: 'Italian Game',      desc: 'Classic 1.e4 e5 (Center Control)',    fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3' },
  { id: 'ruy',      name: 'Ruy Lopez',          desc: 'Spanish Opening (Pressure on Knight)', fen: 'r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3' },
  { id: 'sicilian', name: 'Sicilian Defense',   desc: 'Sharp 1.e4 c5 Counter-Attack',        fen: 'rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2' },
  { id: 'free',     name: 'Standard Free Play', desc: 'Standard Starting Board',             fen: START_FEN },
];

// Helper: convert UCI move (e.g. "e2e4") -> SAN (e.g. "e4") for a given FEN
function uciToSan(fen, from, to) {
  try {
    const g = new Chess(fen);
    const result = g.move({ from, to, promotion: 'q' });
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

export default function CoachPlayScreen({ navigation, route }) {
  // Pre-game state
  const [gameStarted,     setGameStarted]     = useState(false);
  const [selectedColor,   setSelectedColor]   = useState('white');
  const [gameMode,        setGameMode]        = useState('coach');
  const [selectedOpening, setSelectedOpening] = useState('free');
  const [sessionId,       setSessionId]       = useState(null);
  const [startError,      setStartError]      = useState(null);

  // Active game state
  const [fen,           setFen]           = useState(START_FEN);
  const [serverFen,     setServerFen]     = useState(START_FEN);
  const [lastMoveSan,   setLastMoveSan]   = useState('Start');
  const [moveQuality,   setMoveQuality]   = useState('Game Started');
  const [coachAdvice,   setCoachAdvice]   = useState('Welcome! Make your move to start playing.');
  const [loading,       setLoading]       = useState(false);
  const [moveHistory,   setMoveHistory]   = useState([]);
  const [isPlayerTurn,  setIsPlayerTurn]  = useState(true);
  const [gameOver,      setGameOver]      = useState(false);
  const [coachThinking, setCoachThinking] = useState(false);

  // Stats
  const [stats, setStats] = useState({ wins: 0, draws: 0, losses: 1, style: 'The Improviser' });

  // Poll ref — so we can cancel on unmount / restart
  const pollRef      = useRef(null);
  const sessionIdRef = useRef(null);
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => () => { if (pollRef.current) clearTimeout(pollRef.current); }, []);

  // Load player identity
  useEffect(() => {
    (async () => {
      try {
        const d = await getCoachPlayerIdentity();
        if (d) setStats({ wins: d.wins || 0, draws: d.draws || 0, losses: d.losses || 1, style: d.style || 'The Improviser' });
      } catch (_) {}
    })();
  }, []);

  // Monitor navigation parameters to auto-start lessons
  useEffect(() => {
    if (route?.params?.startSkillId) {
      const { startLabel, startKind, startContentRef, startColor } = route.params;
      
      const config = {
        user_color: startColor || 'white',
        game_mode: 'coach',
      };

      if (startKind === 'opening') {
        config.opening_name = startLabel;
        config.opening_key = startContentRef;
      } else if (startKind === 'concept') {
        config.training_focus_cognitive_gap = startContentRef;
      } else if (startKind === 'endgame' || startKind === 'mate_pattern') {
        const fenSetup = ENDGAME_FENS[startContentRef];
        if (fenSetup) {
          config.starting_fen = fenSetup;
        }
      }

      // Trigger start with these settings
      handleStartGame(config);

      // Reset navigation parameters to avoid loops
      navigation.setParams({ startSkillId: null });
    }
  }, [route?.params]);

  // Simple move explanation
  const moveExplanation = (m) => {
    if (!m) return 'Moving pieces into action.';
    const p = m.piece?.toUpperCase();
    if (m.flags?.includes('k') || m.flags?.includes('q')) return 'Castled! King is safe, Rook is active.';
    if (m.flags?.includes('c')) return 'Captured an opponent piece!';
    if (p === 'P' && ['d4','e4','d5','e5'].includes(m.to)) return 'Center pawn push! Fighting for the center.';
    if (p === 'P') return 'Pawn push! Clearing space for your pieces.';
    if (p === 'N') return 'Knight out! Heading toward an active square.';
    if (p === 'B') return 'Bishop active! Aiming down a diagonal.';
    if (p === 'R') return 'Rook on an open file!';
    if (p === 'Q') return 'Queen joins the game!';
    return 'Good development move!';
  };

  const nextMoveHint = (g) => {
    try {
      const isMated = typeof g.isCheckmate === 'function' ? g.isCheckmate() : (typeof g.in_checkmate === 'function' ? g.in_checkmate() : false);
      const isStale = typeof g.isStalemate === 'function' ? g.isStalemate() : (typeof g.in_stalemate === 'function' ? g.in_stalemate() : false);
      const isDrawn = typeof g.isDraw === 'function' ? g.isDraw() : (typeof g.in_draw === 'function' ? g.in_draw() : false);
      
      if (isMated) return '💡 Suggestion: CHECKMATE! The game is already over.';
      if (isStale || isDrawn) return '💡 Suggestion: The game is a draw.';

      const mvs = g.moves({ verbose: true });
      if (!mvs || !mvs.length) return '💡 Suggestion: No legal moves left. Game Over!';

      // Look for check moves
      const checkMove = mvs.find(m => m.san && m.san.includes('+'));
      if (checkMove) return `💡 Suggestion: Try checking the opponent with ${checkMove.san}!`;

      // Look for captures
      const captureMove = mvs.find(m => m.flags?.includes('c') || m.captured);
      if (captureMove) return `💡 Suggestion: You can capture a piece! Try playing ${captureMove.san}.`;

      // Look for castling
      const castle = mvs.find(m => m.flags?.includes('k') || m.flags?.includes('q'));
      if (castle) return `💡 Suggestion: Castle (${castle.san}) to secure your King safety.`;

      // Knight or Bishop developments
      const minorPiece = mvs.find(m => m.piece === 'n' || m.piece === 'b');
      if (minorPiece) return `💡 Suggestion: Develop your minor piece with ${minorPiece.san}.`;

      // Central pawn push
      const centerPawn = mvs.find(m => m.piece === 'p' && ['d4','e4','d5','e5'].includes(m.to));
      if (centerPawn) return `💡 Suggestion: Push your pawn to the center with ${centerPawn.san}.`;

      return `💡 Suggestion: Try playing ${mvs[0].san} to improve your position.`;
    } catch (e) {
      console.log('[CoachPlay] nextMoveHint error:', e);
      return '💡 Suggestion: Develop your Knights and Bishops, then castle to protect your King.';
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
          if (mode === 'coach') {
            try {
              const fb = await fetchAPI('/coach/play/v5/interactive-feedback', {
                method: 'POST',
                body: JSON.stringify({ session_id: sid }),
              });
              console.log('[InteractiveFeedback] Response:', JSON.stringify(fb));
              
              const userAdvice = fb?.user_move_coaching?.narrative || fb?.user_move_coaching?.coaching_message || '';
              const coachAdviceText = fb?.coach_move_coaching?.explanation || fb?.coach_move_coaching?.narrative || '';
              const hintText = fb?.coach_move_coaching?.hint_for_user || '';

              const parts = [];
              if (userAdvice) parts.push(`User Move: ${userAdvice}`);
              if (coachAdviceText) parts.push(`Coach Move: ${coachAdviceText}`);
              if (hintText) parts.push(`Hint: ${hintText}`);
              
              advice = parts.join('\n\n');
            } catch (err) {
              console.log('[InteractiveFeedback] Error:', err);
            }
          }

          const g = new Chess(newFen);
          const hint = nextMoveHint(g);
          if (mode === 'coach') {
            setCoachAdvice(`Opponent played: ${coachSan}\n${advice ? `Coach says: "${advice}"\n\n` : ''}${hint}`);
          } else {
            setCoachAdvice(`Opponent played: ${coachSan}. Your turn!`);
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
          if (res === 'loss') { setMoveQuality('CHECKMATED'); setCoachAdvice('Opponent won. Tap Restart!'); setStats(p => ({ ...p, losses: p.losses + 1 })); }
          else if (res === 'draw') { setMoveQuality('DRAW'); setCoachAdvice('Game ended in a draw!'); setStats(p => ({ ...p, draws: p.draws + 1 })); }
          setGameOver(true); setCoachThinking(false);
          return;
        }
      } catch (_) {}

      if (attempts >= MAX) {
        stopPoll(); setCoachThinking(false); setIsPlayerTurn(true);
        setCoachAdvice('Coach took too long. Your turn!');
        return;
      }
      pollRef.current = setTimeout(poll, 2000);
    };

    pollRef.current = setTimeout(poll, 600);
  }, []);

  const localGameOver = (g, color) => {
    if (g.isCheckmate()) {
      const winner = g.turn() === 'w' ? 'black' : 'white';
      if (winner === color) {
        setMoveQuality('VICTORY!'); setCoachAdvice('YOU WON BY CHECKMATE!');
        setStats(p => ({ ...p, wins: p.wins + 1 }));
      } else {
        setMoveQuality('CHECKMATED'); setCoachAdvice('Opponent won. Tap Restart!');
        setStats(p => ({ ...p, losses: p.losses + 1 }));
      }
    } else if (g.isStalemate() || g.isDraw()) {
      setMoveQuality('DRAW'); setCoachAdvice('Game drawn!');
      setStats(p => ({ ...p, draws: p.draws + 1 }));
    }
    setGameOver(true); setCoachThinking(false);
    if (sessionIdRef.current) endCoachSession(sessionIdRef.current).catch(() => {});
  };

  // =========================================================================
  // Start Game — POST /coach/play/start with CORRECT field names
  // Backend expects: user_color, game_mode, opening_name, starting_fen
  // =========================================================================
  const handleStartGame = async (overrideParams = null) => {
    stopPoll();
    
    // Configurable parameters based on direct selections or learn redirections
    const color = overrideParams?.user_color || selectedColor;
    const mode = overrideParams?.game_mode || gameMode;
    const op = overrideParams ? null : OPENINGS.find(o => o.id === selectedOpening);
    
    let startFen = overrideParams?.starting_fen || op?.fen || START_FEN;
    let openingName = overrideParams?.opening_name || (op?.id !== 'free' ? op?.name : undefined);
    
    setLoading(true); setGameOver(false); setIsPlayerTurn(true);
    setMoveHistory([]); setCoachThinking(false); setStartError(null);

    let newSid = null;
    let useFen = startFen;
    let playerFirst = true;

    try {
      const body = {
        user_color: color,
        game_mode:  mode,
      };
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
        newSid       = res.session_id || res.session?.session_id;
        useFen       = res.current_fen || startFen;
        playerFirst  = res.is_player_turn !== false;
      }
    } catch (e) {
      console.log('[CoachPlay] start fallback:', e?.message);
      setStartError(e?.message || 'Failed to start coach session');
      Alert.alert(
        'Play Limit Reached',
        e?.message || 'You have reached your daily coach session limit. Game is starting in offline fallback mode.',
        [{ text: 'Play Offline', style: 'cancel' }]
      );
      newSid = 'local_' + Date.now();
    }

    setSessionId(newSid);
    sessionIdRef.current = newSid;
    setFen(useFen); setServerFen(useFen);
    setLastMoveSan('Start'); setMoveQuality('Game Started'); setGameStarted(true);

    const g = new Chess(useFen);
    const userChar = color === 'white' ? 'w' : 'b';

    if (!playerFirst || g.turn() !== userChar) {
      setIsPlayerTurn(false); setCoachThinking(true);
      setCoachAdvice(`Game started! Opponent is making their opening move...`);
      startPollForCoachMove(newSid, mode, color);
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

    const curFen = serverFen || fen;

    // Convert board move to SAN (backend needs SAN, not UCI)
    const moveSan = uciToSan(curFen, moveData.from, moveData.to);
    if (!moveSan) { setCoachAdvice('Illegal move!'); return; }

    // Apply locally for instant feedback
    let g;
    try { g = new Chess(curFen); } catch (_) { g = new Chess(START_FEN); }
    const moveResult = g.move({ from: moveData.from, to: moveData.to, promotion: 'q' });
    if (!moveResult) { setCoachAdvice('Illegal move!'); return; }

    const userFen = g.fen();
    setFen(userFen);
    setLastMoveSan(moveSan);
    setMoveHistory(prev => [...prev, moveSan]);
    const exp = moveExplanation(moveResult);

    // Check local game-over (checkmate/stalemate by user's move)
    if (g.isCheckmate()) {
      setMoveQuality('CHECKMATE!');
      setCoachAdvice(`YOU WON BY CHECKMATE WITH ${moveSan}!`);
      setStats(p => ({ ...p, wins: p.wins + 1 }));
      setGameOver(true);
      if (sessionId) endCoachSession(sessionId).catch(() => {});
      return;
    }
    if (g.isStalemate() || g.isDraw()) {
      setMoveQuality('STALEMATE'); setCoachAdvice('Game drawn by stalemate!');
      setStats(p => ({ ...p, draws: p.draws + 1 })); setGameOver(true);
      if (sessionId) endCoachSession(sessionId).catch(() => {});
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
          if (r === 'win') { setMoveQuality('CHECKMATE!'); setCoachAdvice(`You won! ${moveSan} was checkmate!`); setStats(p => ({ ...p, wins: p.wins + 1 })); }
          else if (r === 'draw') { setMoveQuality('DRAW'); setCoachAdvice('Game ended in a draw!'); setStats(p => ({ ...p, draws: p.draws + 1 })); }
          setGameOver(true); setCoachThinking(false);
          if (sessionId) endCoachSession(sessionId).catch(() => {});
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
        setLastMoveSan(pick.san);
        setMoveHistory(prev => [...prev, pick.san]);
        if (ai.isCheckmate()) { localGameOver(ai, selectedColor); return; }
        const hint = nextMoveHint(ai);
        setCoachAdvice(
          gameMode === 'coach'
            ? `You played ${moveSan}: ${exp}\nOpponent: ${pick.san}\n\n${hint}`
            : `You played ${moveSan}. Opponent: ${pick.san}.`
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
        setStats(p => ({ ...p, wins: p.wins + 1 }));
      } else {
        setMoveQuality('CHECKMATED'); setCoachAdvice('Opponent won.');
        setStats(p => ({ ...p, losses: p.losses + 1 }));
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
                {['white','black'].map(c => (
                  <TouchableOpacity key={c} style={[st.colorBtn, selectedColor === c && st.colorBtnOn]} onPress={() => setSelectedColor(c)}>
                    <Text style={st.colorDot}>{c === 'white' ? '⚪' : '🖤'}</Text>
                    <Text style={[st.colorTxt, selectedColor === c && st.colorTxtOn]}>{c === 'white' ? 'White' : 'Black'}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={st.label}>Game Type</Text>
              <View style={st.row}>
                {[
                  { id: 'coach', icon: '🧠', title: 'Coach Mode', sub: 'Real-time teaching & feedback', rec: true },
                  { id: 'play',  icon: '♟️', title: 'Play Mode',  sub: 'Pure chess, no hints' },
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
                  {[['Wins', stats.wins, '#22c55e'],['Draws', stats.draws, '#cbd5e1'],['Losses', stats.losses, '#ef4444']].map(([l, v, c]) => (
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
            {startError && (
              <View style={[st.errCard, { marginBottom: 8, marginTop: 10 }]}>
                <Text style={st.errTitle}>⚠️ Offline Fallback Active</Text>
                <Text style={st.errText}>{startError}</Text>
              </View>
            )}

            {/* Last move + quality at the top */}
            <View style={[st.qualityBar, startError && { marginTop: 0 }]}>
              <View style={st.sanBadge}><Text style={st.sanTxt}>LAST: {lastMoveSan}</Text></View>
              <Text style={[st.qualityTxt, gameOver && { color: '#ef4444' }]}>{moveQuality}</Text>
            </View>

            {/* Coach speech bubble — compact, max 2 lines visible (hidden in Play Mode for pure chess) */}
            {gameMode === 'coach' && (
              <View style={st.bubble}>
                {coachThinking
                  ? <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                      <ActivityIndicator size="small" color="#eab308" />
                      <Text style={st.bubbleTxt}>Coach is thinking...</Text>
                    </View>
                  : <Text style={st.bubbleTxt} numberOfLines={3} ellipsizeMode="tail">{coachAdvice}</Text>
                }
              </View>
            )}

            {/* Chess board — centered, takes available space */}
            <View style={st.board}>
              <ChessBoardView
                fen={fen}
                orientation={selectedColor}
                onMove={handleUserMove}
                onNoMoves={handleNoMoves}
                onGameOver={handleGameOver}
              />
            </View>

            {/* Turn indicator */}
            {!gameOver && (
              <View style={[st.turnBar, { borderColor: isPlayerTurn ? '#22c55e' : '#eab308' }]}>
                <Text style={[st.turnTxt, { color: isPlayerTurn ? '#22c55e' : '#eab308' }]}>
                  {isPlayerTurn ? '✅ YOUR TURN' : '⏳ Coach thinking...'}
                </Text>
              </View>
            )}

            {/* Action buttons including Setup and Restart */}
            <View style={st.controls}>
              {gameMode === 'coach' && isPlayerTurn && !gameOver && (
                <TouchableOpacity style={st.hintBtn} onPress={() => setCoachAdvice(nextMoveHint(new Chess(fen)))}>
                  <Text style={st.hintBtnTxt}>💡 Hint</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={st.restartBtn} onPress={handleStartGame}>
                <Text style={st.restartBtnTxt}>🔄 Restart</Text>
              </TouchableOpacity>
              <TouchableOpacity style={st.setupBtn} onPress={() => { stopPoll(); setGameStarted(false); setGameOver(false); }}>
                <Text style={st.setupBtnTxt}>⚙️ Setup</Text>
              </TouchableOpacity>
            </View>

            {/* AI Coach Status indicator card at the bottom */}
            <View style={st.bottomCoachCard}>
              <Text style={st.bottomCoachText}>
                🧙‍♂️ AI Coach Guru • {gameMode === 'coach' ? 'Coach Mode' : 'Play Mode'}{coachThinking ? ' (Thinking...)' : ''}
              </Text>
            </View>

            {/* Move log strip */}
            <View style={st.logCard}>
              <Text style={st.logTitle}>📜 Moves:</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <Text style={st.logTxt}>
                  {moveHistory.length > 0
                    ? moveHistory.map((s, i) => (i % 2 === 0 ? `${Math.floor(i/2)+1}. ${s}` : s)).join('  ')
                    : 'Awaiting first move...'}
                </Text>
              </ScrollView>
            </View>
          </View>
        )}
      </SafeAreaView>
    </ImageBackground>
  );
}

const st = StyleSheet.create({
  bg:        { flex: 1, width: '100%', height: '100%' },
  overlay:   { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(5,8,16,0.45)' },
  safe:      { flex: 1 },
  scroll:    { flex: 1 },
  content:   { padding: 16, paddingBottom: 40 },

  // Active game — fixed full screen, no scrolling
  gameScreen:{ flex: 1, paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, justifyContent: 'space-between' },

  // Setup
  setupCard: { backgroundColor: 'rgba(15,23,42,0.94)', borderRadius: 26, padding: 22, borderWidth: 1.5, borderColor: 'rgba(234,179,8,0.4)', elevation: 12 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 20 },
  iconCircle:{ width:52, height:52, borderRadius:26, backgroundColor:'rgba(234,179,8,0.2)', justifyContent:'center', alignItems:'center', borderWidth:1.5, borderColor:'#eab308' },
  iconTxt:   { fontSize: 26 },
  setupTitle:{ color:'#fff', fontSize:24, fontWeight:'900' },
  setupSub:  { color:'#cbd5e1', fontSize:13, marginTop:2 },
  label:     { color:'#fff', fontSize:14, fontWeight:'800', marginTop:16, marginBottom:10 },
  row:       { flexDirection:'row', gap:12, marginBottom:14 },

  colorBtn:  { flex:1, flexDirection:'row', alignItems:'center', justifyContent:'center', gap:8, backgroundColor:'rgba(30,41,59,0.85)', borderRadius:18, paddingVertical:14, borderWidth:1.5, borderColor:'rgba(255,255,255,0.18)' },
  colorBtnOn:{ backgroundColor:'rgba(234,179,8,0.25)', borderColor:'#eab308' },
  colorDot:  { fontSize:18 },
  colorTxt:  { color:'#cbd5e1', fontWeight:'800', fontSize:15 },
  colorTxtOn:{ color:'#fef08a', fontWeight:'900' },

  modeCard:  { flex:1, backgroundColor:'rgba(30,41,59,0.85)', borderRadius:20, padding:16, borderWidth:1.5, borderColor:'rgba(255,255,255,0.18)', alignItems:'center', position:'relative' },
  modeCardOn:{ backgroundColor:'rgba(234,179,8,0.25)', borderColor:'#eab308' },
  recTag:    { position:'absolute', top:-10, backgroundColor:'#eab308', paddingHorizontal:8, paddingVertical:3, borderRadius:8 },
  recTxt:    { color:'#000', fontSize:9, fontWeight:'900' },
  modeIcon:  { fontSize:26, marginBottom:6, marginTop:4 },
  modeTitle: { color:'#fff', fontWeight:'900', fontSize:15, marginBottom:3 },
  modeSub:   { color:'#cbd5e1', fontSize:11, textAlign:'center' },

  statsCard: { backgroundColor:'rgba(30,41,59,0.65)', borderRadius:20, padding:16, borderWidth:1, borderColor:'rgba(255,255,255,0.2)', marginVertical:12 },
  statsTitle:{ color:'#fff', fontWeight:'800', fontSize:14, marginBottom:12 },
  statsRow:  { flexDirection:'row', justifyContent:'space-around', marginBottom:12 },
  statBox:   { alignItems:'center' },
  statVal:   { fontSize:22, fontWeight:'900' },
  statLbl:   { color:'#94a3b8', fontSize:12, fontWeight:'700' },
  badgeRow:  { flexDirection:'row', alignItems:'center', gap:8, marginTop:4 },
  badgeLbl:  { color:'#cbd5e1', fontSize:12 },
  badge:     { backgroundColor:'rgba(234,179,8,0.25)', paddingHorizontal:10, paddingVertical:4, borderRadius:10, borderWidth:1, borderColor:'#eab308' },
  badgeTxt:  { color:'#fef08a', fontWeight:'800', fontSize:12 },

  openingGrid:{ gap:10, marginBottom:24 },
  chip:      { flexDirection:'row', alignItems:'center', justifyContent:'space-between', backgroundColor:'rgba(30,41,59,0.85)', borderRadius:16, paddingVertical:14, paddingHorizontal:16, borderWidth:1.5, borderColor:'rgba(255,255,255,0.18)' },
  chipOn:    { backgroundColor:'rgba(234,179,8,0.25)', borderColor:'#eab308' },
  chipTxt:   { color:'#cbd5e1', fontWeight:'800', fontSize:14 },
  chipTxtOn: { color:'#fef08a', fontWeight:'900' },
  chipSub:   { color:'#94a3b8', fontSize:11, marginTop:2 },
  checkMark: { color:'#eab308', fontWeight:'900', fontSize:18 },

  startBtn:  { backgroundColor:'#eab308', borderRadius:20, paddingVertical:18, alignItems:'center', elevation:8 },
  startBtnTxt:{ color:'#090d16', fontWeight:'900', fontSize:18 },

  // Active game bottom coach status
  bottomCoachCard: { backgroundColor: 'rgba(15,23,42,0.8)', borderRadius: 12, paddingVertical: 6, paddingHorizontal: 12, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  bottomCoachText: { color: '#cbd5e1', fontSize: 11, fontWeight: '700' },

  qualityBar:{ flexDirection:'row', justifyContent:'space-between', alignItems:'center', backgroundColor:'rgba(15,23,42,0.85)', borderRadius:16, paddingHorizontal:14, paddingVertical:10, borderWidth:1.2, borderColor:'rgba(255,255,255,0.25)', marginBottom:10, marginTop:24 },
  sanBadge:  { backgroundColor:'rgba(234,179,8,0.25)', paddingHorizontal:10, paddingVertical:4, borderRadius:10 },
  sanTxt:    { color:'#fef08a', fontWeight:'900', fontSize:12 },
  qualityTxt:{ color:'#22c55e', fontWeight:'900' },

  bubble:    { backgroundColor:'rgba(15,23,42,0.9)', borderRadius:20, paddingHorizontal:14, paddingVertical:10, borderWidth:1.5, borderColor:'rgba(234,179,8,0.6)', justifyContent:'center' },
  bubbleTxt: { color:'#fff', fontSize:12, fontWeight:'700', lineHeight:17 },

  board:     { alignItems:'center' },

  turnBar:   { borderRadius:10, borderWidth:1.5, paddingVertical:6, paddingHorizontal:14, alignItems:'center', backgroundColor:'rgba(15,23,42,0.75)' },
  turnTxt:   { fontWeight:'800', fontSize:13 },

  controls:  { flexDirection:'row', gap:8 },
  hintBtn:   { flex:1, backgroundColor:'#eab308', borderRadius:14, paddingVertical:12, alignItems:'center' },
  hintBtnTxt:{ color:'#000', fontWeight:'900', fontSize:13 },
  restartBtn:{ flex:1, backgroundColor:'rgba(239, 68, 68, 0.1)', borderRadius:14, paddingVertical:12, alignItems:'center', borderWidth:1.2, borderColor:'#ef4444' },
  restartBtnTxt:{ color:'#ef4444', fontWeight:'900', fontSize:13 },
  setupBtn:  { flex:1, backgroundColor:'rgba(255,255,255,0.1)', borderRadius:14, paddingVertical:12, alignItems:'center', borderWidth:1, borderColor:'rgba(255,255,255,0.3)' },
  setupBtnTxt:{ color:'#fff', fontWeight:'900', fontSize:13 },

  logCard:   { backgroundColor:'rgba(15,23,42,0.85)', borderRadius:16, paddingHorizontal:14, paddingVertical:10, borderWidth:1, borderColor:'rgba(255,255,255,0.2)', flexDirection:'row', alignItems:'center', gap:8 },
  logTitle:  { color:'#94a3b8', fontSize:11, fontWeight:'800' },
  logTxt:    { color:'#fef08a', fontSize:12, fontWeight:'700' },

  errCard:   { backgroundColor: 'rgba(239, 68, 68, 0.15)', borderRadius: 16, padding: 14, borderWidth: 1.2, borderColor: '#ef4444', marginBottom: 16 },
  errTitle:  { color: '#fca5a5', fontWeight: '900', fontSize: 13, marginBottom: 4 },
  errText:   { color: '#fff', fontSize: 12, fontWeight: '600', lineHeight: 17 },
  errSubtext:{ color: '#94a3b8', fontSize: 10, fontWeight: '700', marginTop: 6 },
});
