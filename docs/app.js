// NNUE v2 Silicon Web Client Controller
// Manages board rendering, piece interaction, web worker engine, and sounds

document.addEventListener('DOMContentLoaded', () => {
  const game = new Chess();
  const worker = new Worker('engine.worker.js');

  // State
  let playerColor = 'w';
  let boardOrientation = 'w';
  let selectedSquare = null;
  let legalMoves = [];
  let isEngineThinking = false;
  let searchBudgetMs = 3000;
  let lastMove = null;

  // DOM Elements
  const boardEl = document.getElementById('board');
  const evalBarWhiteEl = document.getElementById('eval-bar-white');
  const evalBarBlackEl = document.getElementById('eval-bar-black');
  const evalScoreLabelEl = document.getElementById('eval-score-label');
  const depthValueEl = document.getElementById('depth-value');
  const nodesValueEl = document.getElementById('nodes-value');
  const npsValueEl = document.getElementById('nps-value');
  const speedValueEl = document.getElementById('speed-value');
  const thoughtEl = document.getElementById('engine-thought');
  const historyListEl = document.getElementById('history-list');
  const statusBannerEl = document.getElementById('status-banner');
  const difficultySelect = document.getElementById('difficulty-select');

  // Audio Synthesizer via Web Audio API (Zero external assets needed)
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

  function playTone(freq, type, duration, gainVal = 0.1) {
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(gainVal, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  }

  function playSound(type) {
    try {
      if (type === 'move') {
        playTone(320, 'sine', 0.08, 0.15);
      } else if (type === 'capture') {
        playTone(220, 'triangle', 0.12, 0.25);
      } else if (type === 'check') {
        playTone(550, 'sawtooth', 0.2, 0.18);
      } else if (type === 'gameover') {
        playTone(440, 'sine', 0.3, 0.2);
        setTimeout(() => playTone(330, 'sine', 0.4, 0.2), 150);
      }
    } catch (e) {
      // Audio autoplay policy
    }
  }

  // High-Resolution SVG Pieces (Standard Unicode / cburnett Vectors)
  const pieceSVGs = {
    wp: `<svg viewBox="0 0 45 45"><path d="m22.5 9c-2.21 0-4 1.79-4 4 0 .89.29 1.71.78 2.38C17.33 16.5 16 18.59 16 21c0 2.03.94 3.84 2.41 5.03-3 1.06-7.41 5.55-7.41 13.47h23c0-7.92-4.41-12.41-7.41-13.47 1.47-1.19 2.41-3 2.41-5.03 0-2.41-1.33-4.5-3.28-5.62.49-.67.78-1.49.78-2.38 0-2.21-1.79-4-4-4z" fill="#fff" stroke="#000" stroke-width="1.5" stroke-linecap="round"/></svg>`,
    wn: `<svg viewBox="0 0 45 45"><path d="M 22,10 C 32.5,11 38.5,18 38,39 L 15,39 C 15,30 25,32.5 23,18" fill="#fff" stroke="#000" stroke-width="1.5"/><path d="M 24,18 C 24.38,20.91 18.45,25.37 16,27 C 13,29 13.18,31.34 11,31 C 9.958,30.06 12.41,27.96 11,28 C 10,28 11.19,29.23 10,30 C 9,30 5.997,31 6,26 C 6,24 12,14 12,14 C 12,14 13.89,12.1 14,10.5 C 13.27,9.506 13.5,8.5 13.5,7.5 C 14.5,6.5 16.5,10 16.5,10 L 18.5,10 C 18.5,10 19.28,8.008 21,7 C 22,7 22,10 22,10" fill="#fff" stroke="#000" stroke-width="1.5"/></svg>`,
    wb: `<svg viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><g fill="#fff"><path d="M9 36c3.39-.97 10.11.43 13.5-2 3.39 2.43 10.11 1.03 13.5 2 0 0 1.65.54 3 2-.68.97-1.65.99-3 .5-3.39-.97-10.11.46-13.5-1-3.39 1.46-10.11.03-13.5 1-1.354.49-2.323.47-3-.5 1.354-1.94 3-2 3-2zM15 32c2.5 2.5 12.5 2.5 15 0 .5-1.5 0-2 0-2 0-2.5-2.5-4-2.5-4 5.5-1.5 6-11.5-5-15.5-11 4-10.5 14-5 15.5 0 0-2.5 1.5-2.5 4 0 0-.5.5 0 2zM25 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0z"/><path d="M17.5 26h10M15 30h15M22.5 15.5v5M20 18h5"/></g></g></svg>`,
    wr: `<svg viewBox="0 0 45 45"><g fill="#fff" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 39h27v-3H9v3zM12 36v-4h21v4H12zM11 14V9h4v2h5V9h5v2h5V9h4v5" stroke-linecap="butt"/><path d="M34 14l-3 3H14l-3-3"/><path d="M31 17v12.5H14V17"/><path d="M31 29.5l1.5 2.5h-20l1.5-2.5"/></g></svg>`,
    wq: `<svg viewBox="0 0 45 45"><g fill="#fff" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 12a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM24.5 7.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM41 12a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM16 8.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM33 8.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0z"/><path d="M9 26c8.5-1.5 21-1.5 27 0l2-12-7 11-6.5-13.5-6.5 13.5-7-11 2 12zM9 26c0 2 1.5 2 2.5 4 1 1.5 1 1 .5 3.5-1.5 1-1.5 2.5-1.5 2.5-1.5 1.5.5 2.5.5 2.5 6.5 1 16.5 1 23 0 0 0 2-1 .5-2.5 0 0 0-1.5-1.5-2.5-.5-2.5-.5-2 .5-3.5 1-2 2.5-2 2.5-4-8.5-1.5-18.5-1.5-27 0z"/></g></svg>`,
    wk: `<svg viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22.5 11.63V6M20 8h5" stroke-linejoin="miter"/><path d="M22.5 25s4.5-7.5 3-10.5c0 0-1-2.5-3-2.5s-3 2.5-3 2.5c-1.5 3 3 10.5 3 10.5" fill="#fff"/><path d="M11.5 37c5.5 3.5 16.5 3.5 22 0v-4c-5.5 4-16.5 4-22 0v4z" fill="#fff"/><path d="M12 30c5.5-3 15.5-3 21 0v-3c-5.5-3-15.5-3-21 0v3z" fill="#fff"/><path d="M12 33.5c6-3.5 15-3.5 21 0" fill="#fff"/></g></svg>`,
    bp: `<svg viewBox="0 0 45 45"><path d="m22.5 9c-2.21 0-4 1.79-4 4 0 .89.29 1.71.78 2.38C17.33 16.5 16 18.59 16 21c0 2.03.94 3.84 2.41 5.03-3 1.06-7.41 5.55-7.41 13.47h23c0-7.92-4.41-12.41-7.41-13.47 1.47-1.19 2.41-3 2.41-5.03 0-2.41-1.33-4.5-3.28-5.62.49-.67.78-1.49.78-2.38 0-2.21-1.79-4-4-4z" fill="#1e293b" stroke="#000" stroke-width="1.5" stroke-linecap="round"/></svg>`,
    bn: `<svg viewBox="0 0 45 45"><path d="M 22,10 C 32.5,11 38.5,18 38,39 L 15,39 C 15,30 25,32.5 23,18" fill="#1e293b" stroke="#000" stroke-width="1.5"/><path d="M 24,18 C 24.38,20.91 18.45,25.37 16,27 C 13,29 13.18,31.34 11,31 C 9.958,30.06 12.41,27.96 11,28 C 10,28 11.19,29.23 10,30 C 9,30 5.997,31 6,26 C 6,24 12,14 12,14 C 12,14 13.89,12.1 14,10.5 C 13.27,9.506 13.5,8.5 13.5,7.5 C 14.5,6.5 16.5,10 16.5,10 L 18.5,10 C 18.5,10 19.28,8.008 21,7 C 22,7 22,10 22,10" fill="#1e293b" stroke="#000" stroke-width="1.5"/></svg>`,
    bb: `<svg viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><g fill="#1e293b"><path d="M9 36c3.39-.97 10.11.43 13.5-2 3.39 2.43 10.11 1.03 13.5 2 0 0 1.65.54 3 2-.68.97-1.65.99-3 .5-3.39-.97-10.11.46-13.5-1-3.39 1.46-10.11.03-13.5 1-1.354.49-2.323.47-3-.5 1.354-1.94 3-2 3-2zM15 32c2.5 2.5 12.5 2.5 15 0 .5-1.5 0-2 0-2 0-2.5-2.5-4-2.5-4 5.5-1.5 6-11.5-5-15.5-11 4-10.5 14-5 15.5 0 0-2.5 1.5-2.5 4 0 0-.5.5 0 2zM25 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0z"/><path d="M17.5 26h10M15 30h15M22.5 15.5v5M20 18h5"/></g></g></svg>`,
    br: `<svg viewBox="0 0 45 45"><g fill="#1e293b" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 39h27v-3H9v3zM12 36v-4h21v4H12zM11 14V9h4v2h5V9h5v2h5V9h4v5" stroke-linecap="butt"/><path d="M34 14l-3 3H14l-3-3"/><path d="M31 17v12.5H14V17"/><path d="M31 29.5l1.5 2.5h-20l1.5-2.5"/></g></svg>`,
    bq: `<svg viewBox="0 0 45 45"><g fill="#1e293b" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 12a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM24.5 7.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM41 12a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM16 8.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0zM33 8.5a2 2 0 1 1-4 0 2 2 0 1 1 4 0z"/><path d="M9 26c8.5-1.5 21-1.5 27 0l2-12-7 11-6.5-13.5-6.5 13.5-7-11 2 12zM9 26c0 2 1.5 2 2.5 4 1 1.5 1 1 .5 3.5-1.5 1-1.5 2.5-1.5 2.5-1.5 1.5.5 2.5.5 2.5 6.5 1 16.5 1 23 0 0 0 2-1 .5-2.5 0 0 0-1.5-1.5-2.5-.5-2.5-.5-2 .5-3.5 1-2 2.5-2 2.5-4-8.5-1.5-18.5-1.5-27 0z"/></g></svg>`,
    bk: `<svg viewBox="0 0 45 45"><g fill="none" fill-rule="evenodd" stroke="#000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22.5 11.63V6M20 8h5" stroke-linejoin="miter"/><path d="M22.5 25s4.5-7.5 3-10.5c0 0-1-2.5-3-2.5s-3 2.5-3 2.5c-1.5 3 3 10.5 3 10.5" fill="#1e293b"/><path d="M11.5 37c5.5 3.5 16.5 3.5 22 0v-4c-5.5 4-16.5 4-22 0v4z" fill="#1e293b"/><path d="M12 30c5.5-3 15.5-3 21 0v-3c-5.5-3-15.5-3-21 0v3z" fill="#1e293b"/><path d="M12 33.5c6-3.5 15-3.5 21 0" fill="#1e293b"/></g></svg>`
  };

  function updateEvalBar(scoreCp) {
    // Sigmoid win probability: p = 1 / (1 + 10^(-cp / 400))
    let whiteWinProb = 1.0 / (1.0 + Math.pow(10, -scoreCp / 400.0));
    if (scoreCp > 2500) whiteWinProb = 0.99;
    if (scoreCp < -2500) whiteWinProb = 0.01;

    const blackHeightPct = ((1.0 - whiteWinProb) * 100).toFixed(1);
    evalBarBlackEl.style.height = `${blackHeightPct}%`;

    const cpDisplay = (scoreCp >= 0 ? '+' : '') + (scoreCp / 100).toFixed(1);
    evalScoreLabelEl.textContent = cpDisplay;
  }

  function renderBoard() {
    boardEl.innerHTML = '';
    const inCheck = game.in_check();
    const turn = game.turn();

    for (let displayRow = 0; displayRow < 8; displayRow++) {
      for (let displayCol = 0; displayCol < 8; displayCol++) {
        const fileIdx = boardOrientation === 'w' ? displayCol : 7 - displayCol;
        const rankIdx = boardOrientation === 'w' ? 7 - displayRow : displayRow;
        const squareName = String.fromCharCode(97 + fileIdx) + (rankIdx + 1);

        const isLight = (fileIdx + rankIdx) % 2 !== 0;
        const sqEl = document.createElement('div');
        sqEl.className = `square ${isLight ? 'light' : 'dark'}`;
        sqEl.dataset.square = squareName;

        // Coordinate labels
        if ((boardOrientation === 'w' && fileIdx === 0) || (boardOrientation === 'b' && fileIdx === 7)) {
          const rankLabel = document.createElement('span');
          rankLabel.className = 'coord-label rank';
          rankLabel.textContent = rankIdx + 1;
          sqEl.appendChild(rankLabel);
        }
        if ((boardOrientation === 'w' && rankIdx === 0) || (boardOrientation === 'b' && rankIdx === 7)) {
          const fileLabel = document.createElement('span');
          fileLabel.className = 'coord-label file';
          fileLabel.textContent = String.fromCharCode(97 + fileIdx);
          sqEl.appendChild(fileLabel);
        }

        // Highlight selected
        if (selectedSquare === squareName) {
          sqEl.classList.add('selected');
        }

        // Highlight last move
        if (lastMove && (lastMove.from === squareName || lastMove.to === squareName)) {
          sqEl.classList.add('last-move');
        }

        // Piece on square
        const piece = game.get(squareName);
        if (piece) {
          // Highlight check on King
          if (inCheck && piece.type === 'k' && piece.color === turn) {
            sqEl.classList.add('in-check');
          }

          const pieceEl = document.createElement('div');
          pieceEl.className = 'piece';
          const pieceKey = piece.color + piece.type;
          pieceEl.innerHTML = pieceSVGs[pieceKey] || '';
          pieceEl.draggable = (piece.color === playerColor && !isEngineThinking && !game.game_over());
          pieceEl.dataset.square = squareName;

          // Drag Events
          pieceEl.addEventListener('dragstart', onDragStart);
          pieceEl.addEventListener('dragend', onDragEnd);

          sqEl.appendChild(pieceEl);
        }

        // Legal move indicators
        const matchingMove = legalMoves.find(m => m.to === squareName);
        if (matchingMove) {
          if (matchingMove.captured) {
            const ring = document.createElement('div');
            ring.className = 'square-ring';
            sqEl.appendChild(ring);
          } else {
            const dot = document.createElement('div');
            dot.className = 'square-dot';
            sqEl.appendChild(dot);
          }
        }

        // Drop & Click Events
        sqEl.addEventListener('dragover', e => e.preventDefault());
        sqEl.addEventListener('drop', onDrop);
        sqEl.addEventListener('click', () => onSquareClick(squareName));

        boardEl.appendChild(sqEl);
      }
    }
  }

  function updateStatus() {
    if (game.in_checkmate()) {
      const winner = game.turn() === 'w' ? 'Black' : 'White';
      statusBannerEl.className = 'status-banner checkmate';
      statusBannerEl.textContent = `Checkmate! ${winner} wins.`;
      playSound('gameover');
    } else if (game.in_draw()) {
      statusBannerEl.className = 'status-banner draw';
      statusBannerEl.textContent = 'Game Drawn (Stalemate / 3-fold repetition / 50 moves).';
      playSound('gameover');
    } else if (game.in_check()) {
      const checkedColor = game.turn() === 'w' ? 'White' : 'Black';
      statusBannerEl.className = 'status-banner checkmate';
      statusBannerEl.textContent = `Check! ${checkedColor} is attacked.`;
    } else {
      const side = game.turn() === 'w' ? 'White' : 'Black';
      statusBannerEl.className = 'status-banner';
      statusBannerEl.textContent = isEngineThinking ? `NNUE v2 Silicon is calculating...` : `${side} to move.`;
    }
  }

  function updateHistory() {
    const history = game.history({ verbose: true });
    historyListEl.innerHTML = '';
    for (let i = 0; i < history.length; i += 2) {
      const row = document.createElement('div');
      row.className = 'history-row';

      const num = document.createElement('span');
      num.className = 'history-num';
      num.textContent = `${Math.floor(i / 2) + 1}.`;
      row.appendChild(num);

      const wMove = document.createElement('span');
      wMove.className = 'history-move';
      wMove.textContent = history[i].san;
      row.appendChild(wMove);

      if (history[i + 1]) {
        const bMove = document.createElement('span');
        bMove.className = 'history-move';
        bMove.textContent = history[i + 1].san;
        row.appendChild(bMove);
      }
      historyListEl.appendChild(row);
    }
    historyListEl.scrollTop = historyListEl.scrollHeight;
  }

  function executeMove(moveObj) {
    const moveResult = game.move(moveObj);
    if (!moveResult) return false;

    lastMove = moveResult;
    selectedSquare = null;
    legalMoves = [];

    if (moveResult.captured) {
      playSound('capture');
    } else if (game.in_check()) {
      playSound('check');
    } else {
      playSound('move');
    }

    renderBoard();
    updateStatus();
    updateHistory();

    // Trigger NNUE evaluation for the new position
    worker.postMessage({ action: 'evaluate', fen: game.fen() });

    // Trigger Engine reply if it's engine's turn
    if (!game.game_over() && game.turn() !== playerColor) {
      triggerEngineMove();
    }

    return true;
  }

  function triggerEngineMove() {
    isEngineThinking = true;
    updateStatus();
    worker.postMessage({
      action: 'start_search',
      fen: game.fen(),
      budgetMs: searchBudgetMs,
      maxDepth: 30
    });
  }

  // Click & Drag Handlers
  let draggedFromSquare = null;

  function onDragStart(e) {
    draggedFromSquare = e.target.dataset.square;
    selectedSquare = draggedFromSquare;
    legalMoves = game.moves({ square: selectedSquare, verbose: true });
    e.target.classList.add('dragging');
  }

  function onDragEnd(e) {
    e.target.classList.remove('dragging');
    draggedFromSquare = null;
  }

  function onDrop(e) {
    e.preventDefault();
    const toSquare = e.currentTarget.dataset.square;
    if (draggedFromSquare && toSquare) {
      executeMove({
        from: draggedFromSquare,
        to: toSquare,
        promotion: 'q' // default queen promotion for simple play
      });
    }
  }

  function onSquareClick(square) {
    if (isEngineThinking || game.game_over()) return;

    if (selectedSquare) {
      const move = legalMoves.find(m => m.to === square);
      if (move) {
        executeMove(move);
        return;
      }
    }

    const piece = game.get(square);
    if (piece && piece.color === playerColor && piece.color === game.turn()) {
      selectedSquare = square;
      legalMoves = game.moves({ square: selectedSquare, verbose: true });
    } else {
      selectedSquare = null;
      legalMoves = [];
    }
    renderBoard();
  }

  // Worker Response Dispatcher
  worker.onmessage = function (e) {
    const data = e.data;
    if (data.type === 'search_progress') {
      depthValueEl.textContent = data.depth;
      nodesValueEl.textContent = Number(data.nodes).toLocaleString();
      npsValueEl.textContent = `${Math.round(data.nps / 1000)}k`;
      speedValueEl.textContent = `${data.timeMs}ms`;

      // Eval bar from White's perspective
      const whitePerspectiveScore = game.turn() === 'w' ? data.score : -data.score;
      updateEvalBar(whitePerspectiveScore);

      if (data.bestMove) {
        thoughtEl.textContent = `depth ${data.depth} | pv ${data.bestMove.san || data.bestMove.from + data.bestMove.to} | eval ${(whitePerspectiveScore / 100).toFixed(1)}`;
      }
    } else if (data.type === 'search_complete') {
      isEngineThinking = false;
      depthValueEl.textContent = data.depth || 1;
      nodesValueEl.textContent = Number(data.nodes || 0).toLocaleString();
      speedValueEl.textContent = `${data.timeMs || 0}ms`;

      if (data.bestMove && !game.game_over()) {
        executeMove(data.bestMove);
      }
    } else if (data.type === 'eval_result') {
      const whiteScore = game.turn() === 'w' ? data.score : -data.score;
      updateEvalBar(whiteScore);
    }
  };

  // UI Event Listeners
  document.getElementById('btn-new-game').addEventListener('click', () => {
    worker.postMessage({ action: 'stop' });
    worker.postMessage({ action: 'clear_tt' });
    game.reset();
    selectedSquare = null;
    legalMoves = [];
    lastMove = null;
    isEngineThinking = false;
    renderBoard();
    updateStatus();
    updateHistory();
    worker.postMessage({ action: 'evaluate', fen: game.fen() });

    if (playerColor === 'b') {
      triggerEngineMove();
    }
  });

  document.getElementById('btn-flip-board').addEventListener('click', () => {
    boardOrientation = boardOrientation === 'w' ? 'b' : 'w';
    renderBoard();
  });

  document.getElementById('btn-play-white').addEventListener('click', () => {
    playerColor = 'w';
    boardOrientation = 'w';
    document.getElementById('btn-new-game').click();
  });

  document.getElementById('btn-play-black').addEventListener('click', () => {
    playerColor = 'b';
    boardOrientation = 'b';
    document.getElementById('btn-new-game').click();
  });

  document.getElementById('btn-undo').addEventListener('click', () => {
    if (isEngineThinking) return;
    // Undo both engine's move and player's move
    game.undo();
    game.undo();
    lastMove = null;
    selectedSquare = null;
    legalMoves = [];
    renderBoard();
    updateStatus();
    updateHistory();
    worker.postMessage({ action: 'evaluate', fen: game.fen() });
  });

  difficultySelect.addEventListener('change', (e) => {
    searchBudgetMs = parseInt(e.target.value, 10);
  });

  // Initial setup
  renderBoard();
  updateStatus();
  worker.postMessage({ action: 'evaluate', fen: game.fen() });
});
