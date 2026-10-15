importScripts('chess.min.js', 'weights_data.js');

const ChessEngine = (typeof self !== 'undefined' && self.Chess) || (typeof Chess !== 'undefined' ? Chess : (typeof global !== 'undefined' && global.Chess));

const weights = self.NNUE_WEIGHTS.getEmbeddedWeights();
const ptMap = { p: 0, n: 1, b: 2, r: 3, q: 4, k: 5 };
const pieceVal = { p: 100, n: 320, b: 330, r: 500, q: 900, k: 10000 };

function squareToIdx(sqStr) {
  const f = sqStr.charCodeAt(0) - 97;
  const r = parseInt(sqStr[1], 10) - 1;
  return r * 8 + f;
}

function nnueFullRefresh(c) {
  const acc = [new Int16Array(256), new Int16Array(256)];
  acc[0].set(weights.b_acc);
  acc[1].set(weights.b_acc);
  const board = c.board();
  let count = 0;
  for (let r = 0; r < 8; r++) {
    for (let f = 0; f < 8; f++) {
      const piece = board[r][f];
      if (!piece) continue;
      count++;
      const sq = (7 - r) * 8 + f;
      const col = piece.color === 'w' ? 0 : 1;
      const pt = ptMap[piece.type];
      const w_idx = col * 384 + pt * 64 + sq;
      const b_idx = (col ^ 1) * 384 + pt * 64 + (sq ^ 56);
      const w_off = w_idx * 256;
      const b_off = b_idx * 256;
      for (let j = 0; j < 256; j++) {
        acc[0][j] += weights.w_acc[w_off + j];
        acc[1][j] += weights.w_acc[b_off + j];
      }
    }
  }
  return { acc, pieceCount: count };
}

function applyDiff(acc, sign, col, pt, sq) {
  const w_idx = col * 384 + pt * 64 + sq;
  const b_idx = (col ^ 1) * 384 + pt * 64 + (sq ^ 56);
  const w_off = w_idx * 256;
  const b_off = b_idx * 256;
  if (sign === 1) {
    for (let j = 0; j < 256; j++) {
      acc[0][j] += weights.w_acc[w_off + j];
      acc[1][j] += weights.w_acc[b_off + j];
    }
  } else {
    for (let j = 0; j < 256; j++) {
      acc[0][j] -= weights.w_acc[w_off + j];
      acc[1][j] -= weights.w_acc[b_off + j];
    }
  }
}

function nnueEvalHead(acc, turn, totalPieces) {
  const opp = turn ^ 1;
  let bucket = 0;
  if (totalPieces > 6) bucket = 1;
  if (totalPieces > 10) bucket = 2;
  if (totalPieces > 14) bucket = 3;
  if (totalPieces > 18) bucket = 4;
  if (totalPieces > 22) bucket = 5;
  if (totalPieces > 26) bucket = 6;
  if (totalPieces > 29) bucket = 7;

  let out = weights.b_fc2[bucket];
  const w2_offset = bucket * 64;

  const c_acc = new Int32Array(512);
  const acc_turn = acc[turn];
  const acc_opp = acc[opp];
  for (let i = 0; i < 256; i++) {
    let v = acc_turn[i];
    c_acc[i] = v < 0 ? 0 : (v > 127 ? 127 : v);
  }
  for (let i = 0; i < 256; i++) {
    let v = acc_opp[i];
    c_acc[256 + i] = v < 0 ? 0 : (v > 127 ? 127 : v);
  }

  for (let i = 0; i < 64; i++) {
    let s = weights.b_fc1[i];
    const w1_offset = i * 512;
    for (let j = 0; j < 512; j++) {
      s += c_acc[j] * weights.w_fc1[w1_offset + j];
    }
    s = Math.floor(s / 64);
    if (s < 0) s = 0;
    else if (s > 127) s = 127;
    if (i >= 32) {
      s = Math.floor((s * s) / 127);
    }
    out += s * weights.w_fc2[w2_offset + i];
  }

  return Math.floor((out * 173718) / 11117326);
}

// ---------------------------------------------------------------------------
// Transposition Table
// ---------------------------------------------------------------------------
const TT_EXACT = 0;
const TT_LOWER = 1;
const TT_UPPER = 2;
const MATE_VALUE = 30000;

const tt = new Map();
const MAX_TT_ENTRIES = 200000;

function clearTT() {
  tt.clear();
}

// History table & Killers
const historyTable = new Int32Array(64 * 64);
const killers = new Array(128).fill(null).map(() => [null, null]);

function getMoveScore(m, ttMove, ply) {
  if (ttMove && m.from === ttMove.from && m.to === ttMove.to && m.promotion === ttMove.promotion) {
    return 10000000;
  }
  if (m.promotion) {
    return 9000000 + (pieceVal[m.promotion] || 0);
  }
  if (m.captured) {
    const victimVal = pieceVal[m.captured] || 100;
    const attackerVal = pieceVal[m.piece] || 100;
    return 8000000 + victimVal * 10 - attackerVal;
  }
  if (killers[ply] && killers[ply][0] && m.from === killers[ply][0].from && m.to === killers[ply][0].to) {
    return 7000000;
  }
  if (killers[ply] && killers[ply][1] && m.from === killers[ply][1].from && m.to === killers[ply][1].to) {
    return 6000000;
  }
  const fr = squareToIdx(m.from);
  const to = squareToIdx(m.to);
  return historyTable[fr * 64 + to] || 0;
}

// ---------------------------------------------------------------------------
// Quiescence Search
// ---------------------------------------------------------------------------
function qsearch(chess, alpha, beta, ply, acc, pieceCount, searchCtx) {
  searchCtx.nodes++;

  if ((searchCtx.nodes & 511) === 0) {
    if (Date.now() >= searchCtx.deadline) {
      searchCtx.aborted = true;
      return alpha;
    }
  }

  if (ply >= 64) {
    const turn = chess.turn() === 'w' ? 0 : 1;
    return nnueEvalHead(acc, turn, pieceCount);
  }

  const inCheck = chess.in_check();
  let standPat = -Infinity;

  if (!inCheck) {
    const turn = chess.turn() === 'w' ? 0 : 1;
    standPat = nnueEvalHead(acc, turn, pieceCount);
    if (standPat >= beta) return standPat;
    if (standPat > alpha) alpha = standPat;
  }

  let moves = chess.moves({ verbose: true });
  if (!inCheck) {
    moves = moves.filter(m => m.captured || m.promotion);
  }

  if (moves.length === 0) {
    if (inCheck) return -(MATE_VALUE - ply);
    return standPat;
  }

  moves.sort((a, b) => getMoveScore(b, null, ply) - getMoveScore(a, null, ply));

  for (let i = 0; i < moves.length; i++) {
    const m = moves[i];
    const col = m.color === 'w' ? 0 : 1;
    const opp = col ^ 1;
    const fr = squareToIdx(m.from);
    const to = squareToIdx(m.to);
    const pt = ptMap[m.piece];
    const newPt = m.promotion ? ptMap[m.promotion] : pt;

    // Apply diffs
    applyDiff(acc, -1, col, pt, fr);
    applyDiff(acc, 1, col, newPt, to);
    let capturedSq = -1;
    if (m.captured) {
      capturedSq = m.flags.includes('e') ? (col === 0 ? to - 8 : to + 8) : to;
      applyDiff(acc, -1, opp, ptMap[m.captured], capturedSq);
    }
    let rookFr = -1, rookTo = -1;
    if (m.flags.includes('k')) {
      rookFr = col === 0 ? squareToIdx('h1') : squareToIdx('h8');
      rookTo = col === 0 ? squareToIdx('f1') : squareToIdx('f8');
      applyDiff(acc, -1, col, 3, rookFr);
      applyDiff(acc, 1, col, 3, rookTo);
    } else if (m.flags.includes('q')) {
      rookFr = col === 0 ? squareToIdx('a1') : squareToIdx('a8');
      rookTo = col === 0 ? squareToIdx('d1') : squareToIdx('d8');
      applyDiff(acc, -1, col, 3, rookFr);
      applyDiff(acc, 1, col, 3, rookTo);
    }

    chess.move(m);
    const nextPieceCount = m.captured ? pieceCount - 1 : pieceCount;
    const score = -qsearch(chess, -beta, -alpha, ply + 1, acc, nextPieceCount, searchCtx);
    chess.undo();

    // Revert diffs
    applyDiff(acc, 1, col, pt, fr);
    applyDiff(acc, -1, col, newPt, to);
    if (capturedSq !== -1) {
      applyDiff(acc, 1, opp, ptMap[m.captured], capturedSq);
    }
    if (rookFr !== -1) {
      applyDiff(acc, 1, col, 3, rookFr);
      applyDiff(acc, -1, col, 3, rookTo);
    }

    if (searchCtx.aborted) return 0;
    if (score >= beta) return score;
    if (score > alpha) alpha = score;
  }

  return alpha;
}

// ---------------------------------------------------------------------------
// Negamax Search with Alpha-Beta
// ---------------------------------------------------------------------------
function negamax(chess, depth, ply, alpha, beta, acc, pieceCount, searchCtx) {
  searchCtx.nodes++;

  if ((searchCtx.nodes & 511) === 0) {
    if (Date.now() >= searchCtx.deadline) {
      searchCtx.aborted = true;
      return 0;
    }
  }

  if (ply > 0) {
    if (chess.in_draw() || chess.in_threefold_repetition()) {
      return 0;
    }
  }

  const inCheck = chess.in_check();
  if (inCheck && depth < 20) {
    depth++;
  }

  const fen = chess.fen();
  const ttEntry = tt.get(fen);
  let ttMove = null;
  const origAlpha = alpha;

  if (ttEntry) {
    ttMove = ttEntry.move;
    if (ttEntry.depth >= depth) {
      let score = ttEntry.score;
      if (score >= MATE_VALUE - 1000) score -= ply;
      else if (score <= -MATE_VALUE + 1000) score += ply;

      if (ttEntry.flag === TT_EXACT) return score;
      if (ttEntry.flag === TT_LOWER && score > alpha) alpha = score;
      if (ttEntry.flag === TT_UPPER && score < beta) beta = score;
      if (alpha >= beta) return score;
    }
  }

  if (depth <= 0) {
    return qsearch(chess, alpha, beta, ply, acc, pieceCount, searchCtx);
  }

  const moves = chess.moves({ verbose: true });
  if (moves.length === 0) {
    if (inCheck) return -(MATE_VALUE - ply);
    return 0;
  }

  moves.sort((a, b) => getMoveScore(b, ttMove, ply) - getMoveScore(a, ttMove, ply));

  let bestScore = -Infinity;
  let bestMove = null;

  for (let i = 0; i < moves.length; i++) {
    const m = moves[i];
    const col = m.color === 'w' ? 0 : 1;
    const opp = col ^ 1;
    const fr = squareToIdx(m.from);
    const to = squareToIdx(m.to);
    const pt = ptMap[m.piece];
    const newPt = m.promotion ? ptMap[m.promotion] : pt;

    // Apply diffs
    applyDiff(acc, -1, col, pt, fr);
    applyDiff(acc, 1, col, newPt, to);
    let capturedSq = -1;
    if (m.captured) {
      capturedSq = m.flags.includes('e') ? (col === 0 ? to - 8 : to + 8) : to;
      applyDiff(acc, -1, opp, ptMap[m.captured], capturedSq);
    }
    let rookFr = -1, rookTo = -1;
    if (m.flags.includes('k')) {
      rookFr = col === 0 ? squareToIdx('h1') : squareToIdx('h8');
      rookTo = col === 0 ? squareToIdx('f1') : squareToIdx('f8');
      applyDiff(acc, -1, col, 3, rookFr);
      applyDiff(acc, 1, col, 3, rookTo);
    } else if (m.flags.includes('q')) {
      rookFr = col === 0 ? squareToIdx('a1') : squareToIdx('a8');
      rookTo = col === 0 ? squareToIdx('d1') : squareToIdx('d8');
      applyDiff(acc, -1, col, 3, rookFr);
      applyDiff(acc, 1, col, 3, rookTo);
    }

    chess.move(m);
    const nextPieceCount = m.captured ? pieceCount - 1 : pieceCount;
    const score = -negamax(chess, depth - 1, ply + 1, -beta, -alpha, acc, nextPieceCount, searchCtx);
    chess.undo();

    // Revert diffs
    applyDiff(acc, 1, col, pt, fr);
    applyDiff(acc, -1, col, newPt, to);
    if (capturedSq !== -1) {
      applyDiff(acc, 1, opp, ptMap[m.captured], capturedSq);
    }
    if (rookFr !== -1) {
      applyDiff(acc, 1, col, 3, rookFr);
      applyDiff(acc, -1, col, 3, rookTo);
    }

    if (searchCtx.aborted) return 0;

    if (score > bestScore) {
      bestScore = score;
      bestMove = m;
    }
    if (score > alpha) {
      alpha = score;
    }
    if (alpha >= beta) {
      if (!m.captured) {
        killers[ply][1] = killers[ply][0];
        killers[ply][0] = m;
        historyTable[fr * 64 + to] += depth * depth;
      }
      break;
    }
  }

  if (!searchCtx.aborted) {
    let flag = TT_EXACT;
    if (bestScore <= origAlpha) flag = TT_UPPER;
    else if (bestScore >= beta) flag = TT_LOWER;

    let storeScore = bestScore;
    if (storeScore >= MATE_VALUE - 1000) storeScore += ply;
    else if (storeScore <= -MATE_VALUE + 1000) storeScore -= ply;

    if (tt.size >= MAX_TT_ENTRIES) {
      tt.clear();
    }
    tt.set(fen, { depth, score: storeScore, flag, move: bestMove });
  }

  return bestScore;
}

// ---------------------------------------------------------------------------
// Iterative Deepening Root Search
// ---------------------------------------------------------------------------
let isRunning = false;
let stopRequested = false;

function searchRoot(fen, budgetMs, maxDepth = 30) {
  isRunning = true;
  stopRequested = false;

  const chess = new ChessEngine(fen);
  const { acc, pieceCount } = nnueFullRefresh(chess);
  const startTime = Date.now();
  const deadline = startTime + budgetMs;

  const searchCtx = {
    nodes: 0,
    startTime,
    deadline,
    aborted: false
  };

  let bestOverallMove = null;
  let bestOverallScore = 0;
  let completedDepth = 0;

  const legalMoves = chess.moves({ verbose: true });
  if (legalMoves.length === 0) {
    postMessage({ type: 'search_complete', bestMove: null, score: 0, depth: 0, nodes: 0 });
    isRunning = false;
    return;
  }
  if (legalMoves.length === 1) {
    postMessage({
      type: 'search_complete',
      bestMove: legalMoves[0],
      score: 0,
      depth: 1,
      nodes: 1,
      timeMs: 1
    });
    isRunning = false;
    return;
  }

  bestOverallMove = legalMoves[0];

  for (let depth = 1; depth <= maxDepth; depth++) {
    searchCtx.aborted = false;
    const score = negamax(chess, depth, 0, -Infinity, Infinity, acc, pieceCount, searchCtx);

    if (searchCtx.aborted || stopRequested) {
      break;
    }

    const ttEntry = tt.get(fen);
    if (ttEntry && ttEntry.move) {
      bestOverallMove = ttEntry.move;
      bestOverallScore = score;
    }
    completedDepth = depth;

    const elapsed = Date.now() - startTime;
    const nps = elapsed > 0 ? Math.round((searchCtx.nodes / elapsed) * 1000) : 0;

    postMessage({
      type: 'search_progress',
      depth: completedDepth,
      score: bestOverallScore,
      nodes: searchCtx.nodes,
      nps,
      timeMs: elapsed,
      bestMove: bestOverallMove
    });

    // If checkmate found or time is half expired, stop
    if (Math.abs(bestOverallScore) >= MATE_VALUE - 1000) break;
    if (elapsed >= budgetMs * 0.5) break;
  }

  const totalElapsed = Date.now() - startTime;
  postMessage({
    type: 'search_complete',
    bestMove: bestOverallMove,
    score: bestOverallScore,
    depth: completedDepth,
    nodes: searchCtx.nodes,
    timeMs: totalElapsed,
    nps: totalElapsed > 0 ? Math.round((searchCtx.nodes / totalElapsed) * 1000) : 0
  });

  isRunning = false;
}

// ---------------------------------------------------------------------------
// Worker Message Dispatcher
// ---------------------------------------------------------------------------
onmessage = function (e) {
  const { action, fen, budgetMs, maxDepth } = e.data;
  if (action === 'start_search') {
    searchRoot(fen, budgetMs || 2000, maxDepth || 30);
  } else if (action === 'evaluate') {
    const c = new ChessEngine(fen);
    const { acc, pieceCount } = nnueFullRefresh(c);
    const turn = c.turn() === 'w' ? 0 : 1;
    const score = nnueEvalHead(acc, turn, pieceCount);
    postMessage({ type: 'eval_result', fen, score, totalPieces: pieceCount });
  } else if (action === 'stop') {
    stopRequested = true;
  } else if (action === 'clear_tt') {
    clearTT();
  }
};
