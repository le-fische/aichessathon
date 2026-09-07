import chess
import numpy as np

class NNUEAccumulator:
    def __init__(self, weights, biases=None):
        """
        weights: (256, 768) numpy array of int16
        biases: (256,) numpy array of int16
        """
        self.weights = weights
        self.biases = biases if biases is not None else np.zeros(256, dtype=np.int16)
        
        self.white_acc = np.zeros(256, dtype=np.int32)
        self.black_acc = np.zeros(256, dtype=np.int32)
        self.stack = []
        
    def copy(self):
        acc = NNUEAccumulator(self.weights, self.biases)
        acc.white_acc = self.white_acc.copy()
        acc.black_acc = self.black_acc.copy()
        acc.stack = [(w.copy(), b.copy()) for w, b in self.stack]
        return acc

    def init_from_board(self, board: chess.Board):
        self.white_acc = self.biases.copy().astype(np.int32)
        self.black_acc = self.biases.copy().astype(np.int32)
        
        for sq, piece in board.piece_map().items():
            self._update_piece(piece.color, piece.piece_type, sq, 1, self.white_acc, self.black_acc)
            
        self.stack = [(self.white_acc.copy(), self.black_acc.copy())]

    def _get_piece_feature(self, color, piece_type, sq, perspective_color):
        c_rel = 0 if color == perspective_color else 1
        sq_rel = sq if perspective_color == chess.WHITE else sq ^ 56
        return c_rel * 384 + (piece_type - 1) * 64 + sq_rel

    def _update_piece(self, color, piece_type, sq, sign, white_acc, black_acc):
        w_idx = self._get_piece_feature(color, piece_type, sq, chess.WHITE)
        b_idx = self._get_piece_feature(color, piece_type, sq, chess.BLACK)
        if sign > 0:
            white_acc += self.weights[:, w_idx]
            black_acc += self.weights[:, b_idx]
        else:
            white_acc -= self.weights[:, w_idx]
            black_acc -= self.weights[:, b_idx]

    def push_move(self, board: chess.Board, move: chess.Move):
        new_white = self.white_acc.copy()
        new_black = self.black_acc.copy()
        
        moved_piece = board.piece_at(move.from_square)
        if moved_piece is None:
            # Should not happen in legal chess moves, but fallback
            self.stack.append((new_white, new_black))
            return
            
        color = moved_piece.color
        pt = moved_piece.piece_type
        
        # 1. Remove the moving piece from from_square
        self._update_piece(color, pt, move.from_square, -1, new_white, new_black)
        
        # 2. Add the moving piece (or promoted piece) to to_square
        new_pt = move.promotion if move.promotion else pt
        self._update_piece(color, new_pt, move.to_square, 1, new_white, new_black)
        
        # 3. Handle captures
        if board.is_en_passant(move):
            ep_sq = chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
            self._update_piece(not color, chess.PAWN, ep_sq, -1, new_white, new_black)
        elif board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
            if captured_piece:
                self._update_piece(captured_piece.color, captured_piece.piece_type, move.to_square, -1, new_white, new_black)
                
        # 4. Handle castling
        if board.is_castling(move):
            if move.to_square == chess.G1:
                self._update_piece(chess.WHITE, chess.ROOK, chess.H1, -1, new_white, new_black)
                self._update_piece(chess.WHITE, chess.ROOK, chess.F1, 1, new_white, new_black)
            elif move.to_square == chess.C1:
                self._update_piece(chess.WHITE, chess.ROOK, chess.A1, -1, new_white, new_black)
                self._update_piece(chess.WHITE, chess.ROOK, chess.D1, 1, new_white, new_black)
            elif move.to_square == chess.G8:
                self._update_piece(chess.BLACK, chess.ROOK, chess.H8, -1, new_white, new_black)
                self._update_piece(chess.BLACK, chess.ROOK, chess.F8, 1, new_white, new_black)
            elif move.to_square == chess.C8:
                self._update_piece(chess.BLACK, chess.ROOK, chess.A8, -1, new_white, new_black)
                self._update_piece(chess.BLACK, chess.ROOK, chess.D8, 1, new_white, new_black)

        self.white_acc = new_white
        self.black_acc = new_black
        self.stack.append((new_white, new_black))

    def pop_move(self):
        if self.stack:
            self.stack.pop()
        if self.stack:
            self.white_acc, self.black_acc = self.stack[-1]
        else:
            self.white_acc.fill(0)
            self.black_acc.fill(0)

class NNUEBoard(chess.Board):
    def __init__(self, fen=chess.STARTING_FEN, accumulator_weights=None, accumulator_biases=None, **kwargs):
        super().__init__(fen, **kwargs)
        if accumulator_weights is not None:
            self.accumulator = NNUEAccumulator(accumulator_weights, accumulator_biases)
            self.accumulator.init_from_board(self)
        else:
            self.accumulator = None

    def push(self, move: chess.Move):
        if self.accumulator:
            self.accumulator.push_move(self, move)
        super().push(move)

    def pop(self):
        move = super().pop()
        if self.accumulator:
            self.accumulator.pop_move()
        return move

    def copy(self, *args, **kwargs):
        board = super().copy(*args, **kwargs)
        if self.accumulator:
            board.accumulator = self.accumulator.copy()
        else:
            board.accumulator = None
        return board
