import glob
import time
import numpy as np

def preprocess_shards(pattern="data/shards/dataset_shard_*.csv", output_path="data/packed_dataset.npz"):
    files = sorted(glob.glob(pattern))
    print(f"Found {len(files)} shards matching {pattern}")
    if not files:
        raise FileNotFoundError("No shard files found!")

    piece_to_pt = {"P": 0, "N": 1, "B": 2, "R": 3, "Q": 4, "K": 5}

    # Pre-allocate arrays for 2,050,000 positions
    max_positions = len(files) * 105_000
    turn_indices = np.full((max_positions, 32), -1, dtype=np.int16)
    opp_indices = np.full((max_positions, 32), -1, dtype=np.int16)
    targets = np.zeros(max_positions, dtype=np.float32)

    total_count = 0
    t0 = time.time()

    for file_idx, fpath in enumerate(files):
        t_shard = time.time()
        shard_count = 0
        with open(fpath, "r") as f:
            header = next(f) # skip header
            for line in f:
                line = line.strip()
                if not line:
                    continue
                comma_idx = line.rfind(",")
                if comma_idx == -1:
                    continue
                fen_str = line[:comma_idx]
                score = float(line[comma_idx+1:])

                tokens = fen_str.split()
                if len(tokens) < 2:
                    continue
                board_part, turn_char = tokens[0], tokens[1]
                is_white = (turn_char == "w")

                sq = 56
                w_idx_list = []
                b_idx_list = []

                for ch in board_part:
                    if ch == "/":
                        sq -= 16
                    elif ch.isdigit():
                        sq += int(ch)
                    else:
                        c = 0 if ch.isupper() else 1
                        pt = piece_to_pt[ch.upper()]
                        w_idx = c * 384 + pt * 64 + sq
                        b_idx = (c ^ 1) * 384 + pt * 64 + (sq ^ 56)
                        w_idx_list.append(w_idx)
                        b_idx_list.append(b_idx)
                        sq += 1

                n_pieces = len(w_idx_list)
                if n_pieces > 32:
                    # Clip if somehow invalid
                    n_pieces = 32

                if is_white:
                    turn_indices[total_count, :n_pieces] = w_idx_list[:n_pieces]
                    opp_indices[total_count, :n_pieces] = b_idx_list[:n_pieces]
                else:
                    turn_indices[total_count, :n_pieces] = b_idx_list[:n_pieces]
                    opp_indices[total_count, :n_pieces] = w_idx_list[:n_pieces]

                target = 1.0 / (1.0 + 10.0 ** (-score / 400.0))
                targets[total_count] = target

                total_count += 1
                shard_count += 1

        print(f"Shard {file_idx+1:02d}/{len(files)} ({fpath}): {shard_count:,} positions in {time.time()-t_shard:.2f}s")

    # Trim to actual size
    turn_indices = turn_indices[:total_count]
    opp_indices = opp_indices[:total_count]
    targets = targets[:total_count]

    print(f"\nFinished parsing {total_count:,} positions in {time.time()-t0:.2f}s!")
    print(f"Saving packed binary dataset to {output_path}...")
    np.savez_compressed(
        output_path,
        turn_indices=turn_indices,
        opp_indices=opp_indices,
        targets=targets
    )
    print("Done! File size on disk:")
    import os
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  {output_path}: {size_mb:.1f} MB")

if __name__ == "__main__":
    preprocess_shards()
