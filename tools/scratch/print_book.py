from tools.ab_arena import build_book
book = build_book(15, 8, 20260910)
for i, fen in enumerate(book):
    print(f"Pair {i} (Games {2*i+1}, {2*i+2}): {fen}")
