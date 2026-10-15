"""
Download and preprocess 50M+ high-depth Stockfish-evaluated positions
from Hugging Face (Lichess/chess-position-evaluations).
"""

import os
import sys
import time
import urllib.request
import numpy as np
import pyarrow.parquet as pq

DATA_URL = "https://huggingface.co/datasets/Lichess/chess-position-evaluations/resolve/main/data/data_0000.parquet"
PARQUET_FILE = "data/data_0000.parquet"
OUTPUT_DIR = "data/shards_50m"
MAX_POSITIONS = 50_000_000
SHARD_SIZE = 5_000_000
MIN_DEPTH = 12

PIECE_TO_PT = {"P": 0, "N": 1, "B": 2, "R": 3, "Q": 4, "K": 5}

def download_file(url, target_path):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if os.path.exists(target_path):
        current_size = os.path.getsize(target_path)
        print(f"File {target_path} already exists ({current_size / (1024*1024):.1f} MB). Checking size...")
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
        if current_size == total_size:
            print("File is already complete. Skipping download.")
            return
        print(f"File incomplete ({current_size}/{total_size} bytes). Resuming download...")
    else:
        current_size = 0

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    if current_size > 0:
        req.add_header("Range", f"bytes={current_size}-")

    print(f"Connecting to Hugging Face to download {url}...")
    with urllib.request.urlopen(req) as resp:
        content_range = resp.headers.get("Content-Range")
        if content_range:
            total_size = int(content_range.split("/")[-1])
        else:
            total_size = int(resp.headers.get("Content-Length", 0)) + current_size

        mode = "ab" if current_size > 0 else "wb"
        downloaded = current_size
        t0 = time.time()
        last_print = t0

        with open(target_path, mode) as f:
            while True:
                chunk = resp.read(1024 * 1024 * 4) # 4 MB chunks
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                
                now = time.time()
                if now - last_print >= 2.0 or downloaded == total_size:
                    speed_mb = (downloaded - current_size) / (now - t0 + 1e-6) / (1024 * 1024)
                    pct = (downloaded / total_size) * 100 if total_size else 0
                    print(f"  Downloading: {downloaded / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB "
                          f"({pct:5.1f}%) | Speed: {speed_mb:.1f} MB/s", flush=True)
                    last_print = now

    print(f"Download complete: {target_path} ({os.path.getsize(target_path)/(1024*1024):.1f} MB)")

def parse_and_pack_dataset():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Check if shards already exist
    existing_shards = sorted([f for f in os.listdir(OUTPUT_DIR) if f.startswith("shard_") and f.endswith(".npz")])
    if len(existing_shards) >= 10:
        print(f"Found {len(existing_shards)} existing shards in {OUTPUT_DIR}. Dataset is already prepared!")
        return

    download_file(DATA_URL, PARQUET_FILE)

    print(f"\nOpening {PARQUET_FILE} with PyArrow...")
    parquet_file = pq.ParquetFile(PARQUET_FILE)
    print(f"Total rows in Parquet: {parquet_file.metadata.num_rows:,}")
    print(f"Filtering for depth >= {MIN_DEPTH} and packing into shards of {SHARD_SIZE:,}...")

    shard_idx = 0
    total_packed = 0

    turn_buf = np.full((SHARD_SIZE, 32), -1, dtype=np.int16)
    opp_buf = np.full((SHARD_SIZE, 32), -1, dtype=np.int16)
    tgt_buf = np.zeros(SHARD_SIZE, dtype=np.float32)
    buf_count = 0

    t_start = time.time()
    batch_count = 0

    for batch in parquet_file.iter_batches(batch_size=200_000, columns=["fen", "cp", "depth", "mate"]):
        batch_count += 1
        fen_arr = batch.column(0).to_pylist()
        cp_arr = batch.column(1).to_pylist()
        depth_arr = batch.column(2).to_pylist()
        mate_arr = batch.column(3).to_pylist()

        for fen_str, cp_val, depth_val, mate_val in zip(fen_arr, cp_arr, depth_arr, mate_arr):
            # Quality filters
            if depth_val is None or depth_val < MIN_DEPTH:
                continue

            if cp_val is not None:
                score_cp = cp_val
            elif mate_val is not None:
                # Convert mate distance to decisive score (+/- 1500 cp)
                score_cp = 1500 if mate_val > 0 else -1500
            else:
                continue

            # Cap extreme blowouts
            if score_cp > 2500:
                score_cp = 2500
            elif score_cp < -2500:
                score_cp = -2500

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
                    pt = PIECE_TO_PT.get(ch.upper())
                    if pt is None:
                        continue
                    w_idx = c * 384 + pt * 64 + sq
                    b_idx = (c ^ 1) * 384 + pt * 64 + (sq ^ 56)
                    w_idx_list.append(w_idx)
                    b_idx_list.append(b_idx)
                    sq += 1

            n_pieces = len(w_idx_list)
            if n_pieces > 32:
                n_pieces = 32

            if is_white:
                turn_buf[buf_count, :n_pieces] = w_idx_list[:n_pieces]
                opp_buf[buf_count, :n_pieces] = b_idx_list[:n_pieces]
            else:
                turn_buf[buf_count, :n_pieces] = b_idx_list[:n_pieces]
                opp_buf[buf_count, :n_pieces] = w_idx_list[:n_pieces]

            # Stockfish Sigmoid Win Probability target: sigma(cp / 400.0)
            target = 1.0 / (1.0 + 10.0 ** (-score_cp / 400.0))
            tgt_buf[buf_count] = target

            buf_count += 1
            total_packed += 1

            if buf_count == SHARD_SIZE:
                shard_path = os.path.join(OUTPUT_DIR, f"shard_{shard_idx:02d}.npz")
                print(f"Saving Shard {shard_idx:02d} ({buf_count:,} positions) to {shard_path}...")
                np.savez_compressed(
                    shard_path,
                    turn_indices=turn_buf,
                    opp_indices=opp_buf,
                    targets=tgt_buf
                )
                print(f"  --> Saved {shard_path} ({os.path.getsize(shard_path)/(1024*1024):.1f} MB)")
                shard_idx += 1
                buf_count = 0
                turn_buf.fill(-1)
                opp_buf.fill(-1)

                if total_packed >= MAX_POSITIONS:
                    break

        elapsed = time.time() - t_start
        rate = total_packed / (elapsed + 1e-6)
        print(f"Processed batch {batch_count} | Packed {total_packed:,} positions ({rate:.0f} pos/sec)", flush=True)

        if total_packed >= MAX_POSITIONS:
            break

    # Save any remaining positions
    if buf_count > 0:
        shard_path = os.path.join(OUTPUT_DIR, f"shard_{shard_idx:02d}.npz")
        print(f"Saving Final Shard {shard_idx:02d} ({buf_count:,} positions) to {shard_path}...")
        np.savez_compressed(
            shard_path,
            turn_indices=turn_buf[:buf_count],
            opp_indices=opp_buf[:buf_count],
            targets=tgt_buf[:buf_count]
        )
        print(f"  --> Saved {shard_path} ({os.path.getsize(shard_path)/(1024*1024):.1f} MB)")

    print(f"\n=======================================================")
    print(f"SUCCESS: Finished packing {total_packed:,} high-depth positions into {OUTPUT_DIR}/")
    print(f"Total time: {time.time()-t_start:.1f}s")
    print(f"=======================================================")

    # Optionally remove raw parquet file to save 2.2 GB disk space
    if os.path.exists(PARQUET_FILE):
        print(f"Cleaning up raw parquet file {PARQUET_FILE} to free disk space...")
        os.remove(PARQUET_FILE)
        print("Raw parquet removed. Disk space recovered.")

if __name__ == "__main__":
    parse_and_pack_dataset()
