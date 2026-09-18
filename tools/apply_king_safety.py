"""Insert a tapered king-shelter term into both evaluations.

The two implementations must produce identical integers on every position:
nsearch imports evaluate from bitboard.py, everything else uses evaluation.py,
and they have silently diverged twice on this project. The arithmetic below is
deliberately written the same way in both files -- plain integers, the same
loop bounds, the same constants -- so a divergence can only come from a typo,
which the random walk will catch.
"""
import pathlib
import re
import shutil
import sys

SRC = pathlib.Path(sys.argv[1])   # build/v11  (control, untouched)
DST = pathlib.Path(sys.argv[2])   # build/ks   (candidate)

# The device shell cannot delete files, so copy the members explicitly rather
# than mirroring the directory and pruning it afterwards.
# MEMBERS = ("agent.py", "search.py", "evaluation.py", "bitboard.py", "nsearch.py")
# (DST / "weights").mkdir(parents=True, exist_ok=True)
# for name in MEMBERS:
#     if (SRC / name).resolve() != (DST / name).resolve():
#         shutil.copyfile(SRC / name, DST / name)
# for tb in sorted((SRC / "weights").glob("*.rtbw")):
#     if tb.resolve() != (DST / "weights" / tb.name).resolve():
#         shutil.copyfile(tb, DST / "weights" / tb.name)

# --------------------------------------------------------------------------
# evaluation.py  (pure Python reference)
# --------------------------------------------------------------------------
PY_HELPER = '''
# King shelter. The piece-square tables reward a castled king's square but say
# nothing about the pawns in front of it, so the search happily walks into a
# position where the shelter is gone and only notices the mate past its
# horizon. Penalise, per file of the three around the king: no friendly pawn
# in front of it, a friendly pawn that has advanced too far to shelter, and a
# file with no enemy pawn on it at all, which is the file a rook or queen
# arrives on. Middlegame only -- the taper takes it to zero as pieces come off,
# which is correct, an exposed king is an asset in the endgame.
_FILE_MASKS = [0x0101010101010101 << f for f in range(8)]

_SHELTER_NO_PAWN = 26
_SHELTER_FAR = {2: 10, 3: 18}
_SHELTER_OPEN_FILE = 18
_SHELTER_CAP = 120


def _king_shelter_penalty(friendly_pawns, enemy_pawns, ksq, is_white):
    king_file = ksq % 8
    king_rank = ksq // 8

    # Three-file window centred on the king, clamped so a king on the a or h
    # file still looks at three real files rather than falling off the board.
    first_file = min(max(king_file - 1, 0), 5)

    penalty = 0
    for f in range(first_file, first_file + 3):
        nearest = 0  # rank distance to the closest sheltering pawn, 0 = none
        for d in range(1, 4):
            r = king_rank + d if is_white else king_rank - d
            if r < 0 or r > 7:
                break
            if friendly_pawns & (1 << (r * 8 + f)):
                nearest = d
                break

        if nearest == 0:
            penalty += _SHELTER_NO_PAWN
        else:
            penalty += _SHELTER_FAR.get(nearest, 0)

        if not (enemy_pawns & _FILE_MASKS[f]):
            penalty += _SHELTER_OPEN_FILE

    return min(penalty, _SHELTER_CAP)

'''

PY_CALL = '''    white_pawns = board.pawns & board.occupied_co[chess.WHITE]
    black_pawns = board.pawns & board.occupied_co[chess.BLACK]
    white_king = (board.kings & board.occupied_co[chess.WHITE]).bit_length() - 1
    black_king = (board.kings & board.occupied_co[chess.BLACK]).bit_length() - 1
    mg_diff -= _king_shelter_penalty(white_pawns, black_pawns, white_king, True)
    mg_diff += _king_shelter_penalty(black_pawns, white_pawns, black_king, False)

'''

text = (DST / "evaluation.py").read_text()
anchor = "def evaluate(board: chess.Board) -> float:"
assert text.count(anchor) == 1, "evaluation.py: evaluate anchor not unique"
text = text.replace(anchor, PY_HELPER.lstrip("\n") + "\n" + anchor)
call_anchor = "    for pt, mask in [\n"
assert text.count(call_anchor) == 1, "evaluation.py: loop anchor not unique"
text = text.replace(call_anchor, PY_CALL + call_anchor)
(DST / "evaluation.py").write_text(text)

# --------------------------------------------------------------------------
# bitboard.py  (numba, the path that actually plays)
# --------------------------------------------------------------------------
NB_HELPER = '''
# Mirror of _king_shelter_penalty in evaluation.py. Same constants, same loop
# bounds, same integer arithmetic. tests/test_evaluate.py compares the two over
# a random walk; if this drifts from the Python version that test is the only
# thing that will notice.
KS_FILE_MASKS = np.array(
    [np.uint64(0x0101010101010101) << np.uint64(f) for f in range(8)],
    dtype=np.uint64,
)

SHELTER_NO_PAWN = 26
SHELTER_FAR_2 = 10
SHELTER_FAR_3 = 18
SHELTER_OPEN_FILE = 18
SHELTER_CAP = 120


@njit(cache=False)
def king_shelter_penalty(friendly_pawns, enemy_pawns, ksq, is_white):
    king_file = ksq % 8
    king_rank = ksq // 8

    first_file = king_file - 1
    if first_file < 0:
        first_file = 0
    if first_file > 5:
        first_file = 5

    penalty = 0
    for f in range(first_file, first_file + 3):
        nearest = 0
        for d in range(1, 4):
            if is_white:
                r = king_rank + d
            else:
                r = king_rank - d
            if r < 0 or r > 7:
                break
            if (friendly_pawns >> np.uint64(r * 8 + f)) & np.uint64(1):
                nearest = d
                break

        if nearest == 0:
            penalty += SHELTER_NO_PAWN
        elif nearest == 2:
            penalty += SHELTER_FAR_2
        elif nearest == 3:
            penalty += SHELTER_FAR_3

        if (enemy_pawns & KS_FILE_MASKS[f]) == np.uint64(0):
            penalty += SHELTER_OPEN_FILE

    if penalty > SHELTER_CAP:
        penalty = SHELTER_CAP
    return penalty


'''

NB_CALL = '''    white_pawns = pieces[PAWN] & colors[WHITE]
    black_pawns = pieces[PAWN] & colors[BLACK]
    white_king = lsb(pieces[KING] & colors[WHITE])
    black_king = lsb(pieces[KING] & colors[BLACK])
    mg_diff -= king_shelter_penalty(white_pawns, black_pawns, white_king, True)
    mg_diff += king_shelter_penalty(black_pawns, white_pawns, black_king, False)

'''

text = (DST / "bitboard.py").read_text()
# The pawn-terms commit (5197c06) also defines FILE_MASKS in bitboard.py, as a
# different shape indexed differently. Two module-level definitions of one name
# means the later one silently wins, and numba does not bounds-check. We use
# KS_FILE_MASKS to avoid the collision. Guard against a future careless merge
# reverting this rename and colliding with the pawn terms.
assert "FILE_MASKS = np.array(\n    [np.uint64(0x0101010101010101)" not in text, (
    "bitboard.py contains the unrenamed king safety FILE_MASKS which will collide "
    "with the pawn terms. Please rename the king safety one to KS_FILE_MASKS."
)
anchor = "@njit(cache=False)\ndef evaluate(pieces, colors, state):"
assert text.count(anchor) == 1, "bitboard.py: evaluate anchor not unique"
text = text.replace(anchor, NB_HELPER.lstrip("\n") + anchor)
# "for pt in range(6)" appears more than once in this file, so anchor on the
# end of the bishop-pair block inside evaluate, which is unique.
call_anchor = "        eg_diff -= 50\n"
assert text.count(call_anchor) == 1, "bitboard.py: bishop-pair anchor not unique"
text = text.replace(call_anchor, call_anchor + "\n" + NB_CALL)
(DST / "bitboard.py").write_text(text)

print("patched:", DST)
for f in ("evaluation.py", "bitboard.py"):
    print(f"  {f}: {len((DST/f).read_text().splitlines())} lines")
