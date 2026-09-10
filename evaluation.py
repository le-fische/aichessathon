import chess

mg_value: dict[chess.PieceType, int] = {
    chess.PAWN: 82,
    chess.KNIGHT: 337,
    chess.BISHOP: 365,
    chess.ROOK: 477,
    chess.QUEEN: 1025,
    chess.KING: 0,
}
eg_value: dict[chess.PieceType, int] = {
    chess.PAWN: 94,
    chess.KNIGHT: 281,
    chess.BISHOP: 297,
    chess.ROOK: 512,
    chess.QUEEN: 936,
    chess.KING: 0,
}


WHITE_PASSED_PAWN_MASKS = [0] * 64
BLACK_PASSED_PAWN_MASKS = [0] * 64

for sq in range(64):
    f = sq % 8
    r = sq // 8
    
    w_mask = 0
    b_mask = 0
    
    for r2 in range(r + 1, 8):
        w_mask |= 1 << (r2 * 8 + f)
        if f > 0: w_mask |= 1 << (r2 * 8 + f - 1)
        if f < 7: w_mask |= 1 << (r2 * 8 + f + 1)
        
    for r2 in range(0, r):
        b_mask |= 1 << (r2 * 8 + f)
        if f > 0: b_mask |= 1 << (r2 * 8 + f - 1)
        if f < 7: b_mask |= 1 << (r2 * 8 + f + 1)
        
    WHITE_PASSED_PAWN_MASKS[sq] = w_mask
    BLACK_PASSED_PAWN_MASKS[sq] = b_mask

FILE_MASKS_EV = [0] * 8
for _f in range(8):
    _m = 0
    for _r in range(8):
        _m |= 1 << (_r * 8 + _f)
    FILE_MASKS_EV[_f] = _m

# Squares in front of a king on the three files around it, two ranks deep.
KING_SHELTER_W_EV = [0] * 64
KING_SHELTER_B_EV = [0] * 64
for _sq in range(64):
    _f, _r = _sq % 8, _sq // 8
    _w, _b = 0, 0
    for _df in (-1, 0, 1):
        _ff = _f + _df
        if _ff < 0 or _ff > 7:
            continue
        for _dr in (1, 2):
            if _r + _dr <= 7:
                _w |= 1 << ((_r + _dr) * 8 + _ff)
            if _r - _dr >= 0:
                _b |= 1 << ((_r - _dr) * 8 + _ff)
    KING_SHELTER_W_EV[_sq] = _w
    KING_SHELTER_B_EV[_sq] = _b

# --- King safety, half 1: pawn shelter and open files ------------------------------
# Must stay identical to bitboard.king_safety_mg. The two evaluations have silently
# diverged twice; the 7,663-position random walk in tests/test_evaluate.py is the gate.
# Middlegame only -- penalties go into mg_diff and never eg_diff, so the existing taper
# retires the term as pieces come off.
KS_MISSING_PAWN = 12
KS_SEMI_OPEN_ADJ = 12
KS_SEMI_OPEN_KING = 18
KS_OPEN_ADJ = 22
KS_OPEN_KING = 33


def king_safety_mg(board: chess.Board) -> int:
    """Middlegame king-safety delta, white minus black. Positive = white safer."""
    w_pawns = board.pawns & board.occupied_co[chess.WHITE]
    b_pawns = board.pawns & board.occupied_co[chess.BLACK]

    penalty = [0, 0]
    for c in (chess.WHITE, chess.BLACK):
        king_bb = board.kings & board.occupied_co[c]
        if not king_bb:
            continue
        ksq = (king_bb & -king_bb).bit_length() - 1
        own_pawns = w_pawns if c == chess.WHITE else b_pawns
        enemy_pawns = b_pawns if c == chess.WHITE else w_pawns
        shelter = KING_SHELTER_W_EV[ksq] if c == chess.WHITE else KING_SHELTER_B_EV[ksq]

        present = min(3, (own_pawns & shelter).bit_count())
        pen = (3 - present) * KS_MISSING_PAWN

        kf = ksq % 8
        for df in (-1, 0, 1):
            f = kf + df
            if f < 0 or f > 7:
                continue
            fm = FILE_MASKS_EV[f]
            if own_pawns & fm:
                continue
            if enemy_pawns & fm:
                pen += KS_SEMI_OPEN_KING if df == 0 else KS_SEMI_OPEN_ADJ
            else:
                pen += KS_OPEN_KING if df == 0 else KS_OPEN_ADJ
        penalty[c] = pen

    return penalty[chess.BLACK] - penalty[chess.WHITE]


PASSED_PAWN_MG = [0, 5, 10, 20, 35, 60, 100, 0]
PASSED_PAWN_EG = [0, 10, 25, 45, 75, 120, 170, 0]
CONNECTED_PASSED_BONUS_MG = 15
CONNECTED_PASSED_BONUS_EG = 25

_pawn_cache = {}

def _pawn_structure(white_pawns: int, black_pawns: int) -> tuple[int, int]:
    key = (white_pawns, black_pawns)
    if key in _pawn_cache:
        return _pawn_cache[key]
        
    mg = 0
    eg = 0
    
    wp_attacks = ((white_pawns << 7) & 0x7f7f7f7f7f7f7f7f) | ((white_pawns << 9) & 0xfefefefefefefefe)
    bp_attacks = ((black_pawns >> 9) & 0x7f7f7f7f7f7f7f7f) | ((black_pawns >> 7) & 0xfefefefefefefefe)
    
    import chess
    for sq in chess.scan_reversed(white_pawns):
        if not (black_pawns & WHITE_PASSED_PAWN_MASKS[sq]):
            rank = sq // 8
            mg += PASSED_PAWN_MG[rank]
            eg += PASSED_PAWN_EG[rank]
            if (1 << sq) & wp_attacks:
                mg += CONNECTED_PASSED_BONUS_MG
                eg += CONNECTED_PASSED_BONUS_EG

    for sq in chess.scan_reversed(black_pawns):
        if not (white_pawns & BLACK_PASSED_PAWN_MASKS[sq]):
            rank = 7 - (sq // 8)
            mg -= PASSED_PAWN_MG[rank]
            eg -= PASSED_PAWN_EG[rank]
            if (1 << sq) & bp_attacks:
                mg -= CONNECTED_PASSED_BONUS_MG
                eg -= CONNECTED_PASSED_BONUS_EG
                
    if len(_pawn_cache) > 16384:
        _pawn_cache.clear()
        
    _pawn_cache[key] = (mg, eg)
    return mg, eg

mg_pawn_table: list[int] = [
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    98,
    134,
    61,
    95,
    68,
    126,
    34,
    -11,
    -6,
    7,
    26,
    31,
    65,
    56,
    25,
    -20,
    -14,
    13,
    6,
    21,
    23,
    12,
    17,
    -23,
    -27,
    -2,
    -5,
    12,
    17,
    6,
    10,
    -25,
    -26,
    -4,
    -4,
    -10,
    3,
    3,
    33,
    -12,
    -35,
    -1,
    -20,
    -23,
    -15,
    24,
    38,
    -22,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
]

eg_pawn_table: list[int] = [
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    178,
    173,
    158,
    134,
    147,
    132,
    165,
    187,
    94,
    100,
    85,
    67,
    56,
    53,
    82,
    84,
    32,
    24,
    13,
    5,
    -2,
    4,
    17,
    17,
    13,
    9,
    -3,
    -7,
    -7,
    -8,
    3,
    -1,
    4,
    7,
    -6,
    1,
    0,
    -5,
    -1,
    -8,
    13,
    8,
    8,
    10,
    13,
    0,
    2,
    -7,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
]

mg_knight_table: list[int] = [
    -167,
    -89,
    -34,
    -49,
    61,
    -97,
    -15,
    -107,
    -73,
    -41,
    72,
    36,
    23,
    62,
    7,
    -17,
    -47,
    60,
    37,
    65,
    84,
    129,
    73,
    44,
    -9,
    17,
    19,
    53,
    37,
    69,
    18,
    22,
    -13,
    4,
    16,
    13,
    28,
    19,
    21,
    -8,
    -23,
    -9,
    12,
    10,
    19,
    17,
    25,
    -16,
    -29,
    -53,
    -12,
    -3,
    -1,
    18,
    -14,
    -19,
    -105,
    -21,
    -58,
    -33,
    -17,
    -28,
    -19,
    -23,
]

eg_knight_table: list[int] = [
    -58,
    -38,
    -13,
    -28,
    -31,
    -27,
    -63,
    -99,
    -25,
    -8,
    -25,
    -2,
    -9,
    -25,
    -24,
    -52,
    -24,
    -20,
    10,
    9,
    -1,
    -9,
    -19,
    -41,
    -17,
    3,
    22,
    22,
    22,
    11,
    8,
    -18,
    -18,
    -6,
    16,
    25,
    16,
    17,
    4,
    -18,
    -23,
    -3,
    -1,
    15,
    10,
    -3,
    -20,
    -22,
    -42,
    -20,
    -10,
    -5,
    -2,
    -20,
    -23,
    -44,
    -29,
    -51,
    -23,
    -15,
    -22,
    -18,
    -50,
    -64,
]

mg_bishop_table: list[int] = [
    -29,
    4,
    -82,
    -37,
    -25,
    -42,
    7,
    -8,
    -26,
    16,
    -18,
    -13,
    30,
    59,
    18,
    -47,
    -16,
    37,
    43,
    40,
    35,
    50,
    37,
    -2,
    -4,
    5,
    19,
    50,
    37,
    37,
    7,
    -2,
    -6,
    13,
    13,
    26,
    34,
    12,
    10,
    4,
    0,
    15,
    15,
    15,
    14,
    27,
    18,
    10,
    4,
    15,
    16,
    0,
    7,
    21,
    33,
    1,
    -33,
    -3,
    -14,
    -21,
    -13,
    -12,
    -39,
    -21,
]

eg_bishop_table: list[int] = [
    -14,
    -21,
    -11,
    -8,
    -7,
    -9,
    -17,
    -24,
    -8,
    -4,
    7,
    -12,
    -3,
    -13,
    -4,
    -14,
    2,
    -8,
    0,
    -1,
    -2,
    6,
    0,
    4,
    -3,
    9,
    12,
    9,
    14,
    10,
    3,
    2,
    -6,
    3,
    13,
    19,
    7,
    10,
    -3,
    -9,
    -12,
    -3,
    8,
    10,
    13,
    3,
    -7,
    -15,
    -14,
    -18,
    -7,
    -1,
    4,
    -9,
    -15,
    -27,
    -23,
    -9,
    -23,
    -5,
    -9,
    -16,
    -5,
    -17,
]

mg_rook_table: list[int] = [
    32,
    42,
    32,
    51,
    63,
    9,
    31,
    43,
    27,
    32,
    58,
    62,
    80,
    67,
    26,
    44,
    -5,
    19,
    26,
    36,
    17,
    45,
    61,
    16,
    -24,
    -11,
    7,
    26,
    24,
    35,
    -8,
    -20,
    -36,
    -26,
    -12,
    -1,
    9,
    -7,
    6,
    -23,
    -45,
    -25,
    -16,
    -17,
    3,
    0,
    -5,
    -33,
    -44,
    -16,
    -20,
    -9,
    -1,
    11,
    -6,
    -71,
    -19,
    -13,
    1,
    17,
    16,
    7,
    -37,
    -26,
]

eg_rook_table: list[int] = [
    13,
    10,
    18,
    15,
    12,
    12,
    8,
    5,
    11,
    13,
    13,
    11,
    -3,
    3,
    8,
    3,
    7,
    7,
    7,
    5,
    4,
    -3,
    -5,
    -3,
    4,
    3,
    13,
    1,
    2,
    1,
    -1,
    2,
    3,
    5,
    8,
    4,
    -5,
    -6,
    -8,
    -11,
    -4,
    0,
    -5,
    -1,
    -7,
    -12,
    -8,
    -16,
    -6,
    -6,
    0,
    2,
    -9,
    -9,
    -11,
    -3,
    -9,
    2,
    3,
    -1,
    -5,
    -13,
    4,
    -20,
]

mg_queen_table: list[int] = [
    -28,
    0,
    29,
    12,
    59,
    44,
    43,
    45,
    -24,
    -39,
    -5,
    1,
    -16,
    57,
    28,
    54,
    -13,
    -17,
    7,
    8,
    29,
    56,
    47,
    57,
    -27,
    -27,
    -16,
    -16,
    -1,
    17,
    -2,
    1,
    -9,
    -26,
    -9,
    -10,
    -2,
    -4,
    3,
    -3,
    -14,
    2,
    -11,
    -2,
    -5,
    2,
    14,
    5,
    -35,
    -8,
    11,
    2,
    8,
    15,
    -3,
    1,
    -1,
    -18,
    -9,
    10,
    -15,
    -25,
    -31,
    -50,
]

eg_queen_table: list[int] = [
    -9,
    22,
    22,
    27,
    27,
    19,
    10,
    20,
    -17,
    20,
    32,
    41,
    58,
    25,
    30,
    0,
    -20,
    6,
    9,
    49,
    47,
    35,
    19,
    9,
    3,
    22,
    24,
    45,
    57,
    40,
    57,
    36,
    -18,
    28,
    19,
    47,
    31,
    34,
    39,
    23,
    -16,
    -27,
    15,
    6,
    9,
    17,
    10,
    5,
    -22,
    -23,
    -30,
    -16,
    -16,
    -23,
    -36,
    -32,
    -33,
    -28,
    -22,
    -43,
    -5,
    -32,
    -20,
    -41,
]

mg_king_table: list[int] = [
    -65,
    23,
    16,
    -15,
    -56,
    -34,
    2,
    13,
    29,
    -1,
    -20,
    -7,
    -8,
    -4,
    -38,
    -29,
    -9,
    24,
    2,
    -16,
    -20,
    6,
    22,
    -22,
    -17,
    -20,
    -12,
    -27,
    -30,
    -25,
    -14,
    -36,
    -49,
    -1,
    -27,
    -39,
    -46,
    -44,
    -33,
    -51,
    -14,
    -14,
    -22,
    -46,
    -44,
    -30,
    -15,
    -27,
    1,
    7,
    -8,
    -64,
    -43,
    -16,
    9,
    8,
    -15,
    36,
    12,
    -54,
    8,
    -28,
    24,
    14,
]

eg_king_table: list[int] = [
    -74,
    -35,
    -18,
    -18,
    -11,
    15,
    4,
    -17,
    -12,
    17,
    14,
    17,
    17,
    38,
    23,
    11,
    10,
    17,
    23,
    15,
    20,
    45,
    44,
    13,
    -8,
    22,
    24,
    27,
    26,
    33,
    26,
    3,
    -18,
    -4,
    21,
    24,
    27,
    23,
    9,
    -11,
    -19,
    -3,
    11,
    21,
    23,
    16,
    7,
    -9,
    -27,
    -11,
    4,
    13,
    14,
    4,
    -5,
    -17,
    -53,
    -34,
    -21,
    -11,
    -28,
    -14,
    -24,
    -43,
]

mg_table: dict[chess.PieceType, list[int]] = {
    chess.PAWN: mg_pawn_table,
    chess.KNIGHT: mg_knight_table,
    chess.BISHOP: mg_bishop_table,
    chess.ROOK: mg_rook_table,
    chess.QUEEN: mg_queen_table,
    chess.KING: mg_king_table,
}

eg_table: dict[chess.PieceType, list[int]] = {
    chess.PAWN: eg_pawn_table,
    chess.KNIGHT: eg_knight_table,
    chess.BISHOP: eg_bishop_table,
    chess.ROOK: eg_rook_table,
    chess.QUEEN: eg_queen_table,
    chess.KING: eg_king_table,
}

gamephase_inc: list[int] = [0, 0, 1, 1, 2, 4, 0]

# Precomputed flat tables indexed by [color][piece_type][square]
TABLE_MG: list[list[list[int]]] = [[[0] * 64 for _ in range(7)] for _ in range(2)]
TABLE_EG: list[list[list[int]]] = [[[0] * 64 for _ in range(7)] for _ in range(2)]

for color in [chess.WHITE, chess.BLACK]:
    for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
        for sq in chess.SQUARES:
            rank = chess.square_rank(sq)
            file = chess.square_file(sq)
            pst_idx = (7 - rank) * 8 + file if color == chess.WHITE else rank * 8 + file

            val_mg = mg_value[pt] + mg_table[pt][pst_idx]
            val_eg = eg_value[pt] + eg_table[pt][pst_idx]

            if color == chess.WHITE:
                TABLE_MG[color][pt][sq] = val_mg
                TABLE_EG[color][pt][sq] = val_eg
            else:
                TABLE_MG[color][pt][sq] = -val_mg
                TABLE_EG[color][pt][sq] = -val_eg


def evaluate(board: chess.Board) -> float:
    mg_diff = 0
    eg_diff = 0
    game_phase = 0
    
    pawn_mg, pawn_eg = _pawn_structure(
        board.pawns & board.occupied_co[chess.WHITE],
        board.pawns & board.occupied_co[chess.BLACK]
    )
    mg_diff += pawn_mg
    eg_diff += pawn_eg
    
    mg_diff += king_safety_mg(board)

    if (board.bishops & board.occupied_co[chess.WHITE]).bit_count() >= 2:
        mg_diff += 30
        eg_diff += 50
    if (board.bishops & board.occupied_co[chess.BLACK]).bit_count() >= 2:
        mg_diff -= 30
        eg_diff -= 50

    for pt, mask in [
        (chess.PAWN, board.pawns),
        (chess.KNIGHT, board.knights),
        (chess.BISHOP, board.bishops),
        (chess.ROOK, board.rooks),
        (chess.QUEEN, board.queens),
        (chess.KING, board.kings),
    ]:
        game_phase += gamephase_inc[pt] * chess.popcount(mask)
        for c in [chess.WHITE, chess.BLACK]:
            c_mask = mask & board.occupied_co[c]
            for sq in chess.scan_reversed(c_mask):
                mg_diff += TABLE_MG[c][pt][sq]
                eg_diff += TABLE_EG[c][pt][sq]

    if board.turn == chess.BLACK:
        mg_diff = -mg_diff
        eg_diff = -eg_diff

    phase = min(game_phase, 24)

    score = float((mg_diff * phase + eg_diff * (24 - phase)) // 24)

    # Basic-mate drive. Piece-square tables give no gradient when the losing
    # side has only a king: every rook shuffle scores the same, so a winning
    # engine wanders until it repeats. Round 17 was drawn this way a rook up.
    # Mate is past the horizon at these depths, so the evaluation has to point
    # at it: force the lone king to the edge and bring the kings together.
    if game_phase <= 6:
        score += _mate_drive(board)

    return score


# Distance from each square to the centre, in king moves. Higher at the edges,
# highest in the corners, which is where a lone king must be driven.
_CENTRE_DISTANCE = [
    max(abs((sq % 8) - 3.5), abs((sq // 8) - 3.5)) for sq in range(64)
]


def _mate_drive(board: chess.Board) -> float:
    """Push the bare king to the edge and walk the winning king towards it.

    Returns 0 unless exactly one side has nothing but a king, so this cannot
    perturb any position where both sides still have material.
    """
    white_bare = not (board.occupied_co[chess.WHITE] & ~board.kings)
    black_bare = not (board.occupied_co[chess.BLACK] & ~board.kings)
    if white_bare == black_bare:
        return 0.0

    winner = chess.WHITE if black_bare else chess.BLACK
    loser_king = board.king(not winner)
    winner_king = board.king(winner)
    if loser_king is None or winner_king is None:
        return 0.0

    file_gap = abs(chess.square_file(winner_king) - chess.square_file(loser_king))
    rank_gap = abs(chess.square_rank(winner_king) - chess.square_rank(loser_king))
    king_gap = file_gap + rank_gap

    drive = 16.0 * _CENTRE_DISTANCE[loser_king] + 4.0 * (14 - king_gap)

    if winner != board.turn:
        drive = -drive
    return drive