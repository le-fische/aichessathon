"""
Large-Scale Multi-Shard PyTorch MPS Trainer for Model B v2 Silicon.
Finalized Beast Architecture:
  1. 768 Feature Sparse Accumulator (256 dims per perspective -> 512 total)
  2. FC1 Dense Layer (512 -> 64) with SCReLU (32 linear, 32 quadratic)
  3. 8 Material / Piece-Count Output Buckets (FC2: 8 x 64 -> 1)
  4. Quantization-Aware Training (QAT) with Straight-Through Estimators (STE)
  5. Stockfish WDL Cross-Entropy Loss trained on 50 Million high-depth positions
"""

import glob
import math
import os
import sys
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

class QuantizeSTE(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, scale, clip_min, clip_max):
        return torch.clamp(torch.round(x * scale), clip_min, clip_max) / scale

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output, None, None, None

def quantize_ste(x, scale, clip_min, clip_max):
    return QuantizeSTE.apply(x, scale, clip_min, clip_max)

class PieceSquareNNUE_V2Silicon(nn.Module):
    def __init__(self, hidden_dim=256, mlp_dim=64, num_buckets=8):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.mlp_dim = mlp_dim
        self.num_buckets = num_buckets
        
        # 768 features + index 768 as padding (zero-out)
        self.embedding = nn.Embedding(769, hidden_dim, padding_idx=768)
        self.bias = nn.Parameter(torch.zeros(hidden_dim))
        
        # FC1: 512 -> mlp_dim (64)
        self.fc1 = nn.Linear(hidden_dim * 2, mlp_dim)
        
        # FC2: 8 material buckets x mlp_dim (64)
        self.fc2_w = nn.Parameter(torch.empty(num_buckets, mlp_dim))
        self.fc2_b = nn.Parameter(torch.zeros(num_buckets))
        
        # Initialize
        nn.init.kaiming_uniform_(self.embedding.weight[:768], a=math.sqrt(5))
        with torch.no_grad():
            self.embedding.weight[768].zero_()
            nn.init.kaiming_uniform_(self.fc1.weight, a=math.sqrt(5))
            nn.init.zeros_(self.fc1.bias)
            nn.init.kaiming_uniform_(self.fc2_w, a=math.sqrt(5))
            nn.init.zeros_(self.fc2_b)

    def forward(self, turn_idx, opp_idx, qat=True):
        if qat:
            emb_w = quantize_ste(self.embedding.weight, 127.0, -127.0, 127.0)
            bias = quantize_ste(self.bias, 127.0, -127.0, 127.0)
            fc1_w = quantize_ste(self.fc1.weight, 64.0, -127.0, 127.0)
            fc1_b = quantize_ste(self.fc1.bias, 64.0 * 127.0, -2147483647.0, 2147483647.0)
            fc2_w = quantize_ste(self.fc2_w, 87.538, -127.0, 127.0)
            fc2_b = quantize_ste(self.fc2_b, 87.538 * 127.0, -2147483647.0, 2147483647.0)
        else:
            emb_w = self.embedding.weight
            bias = self.bias
            fc1_w = self.fc1.weight
            fc1_b = self.fc1.bias
            fc2_w = self.fc2_w
            fc2_b = self.fc2_b

        # 1. Sparse Accumulator
        turn_acc = torch.nn.functional.embedding(turn_idx, emb_w, padding_idx=768).sum(dim=1) + bias
        opp_acc = torch.nn.functional.embedding(opp_idx, emb_w, padding_idx=768).sum(dim=1) + bias

        turn_c = torch.clamp(turn_acc, 0.0, 1.0)
        opp_c = torch.clamp(opp_acc, 0.0, 1.0)
        if qat:
            turn_c = quantize_ste(turn_c, 127.0, 0.0, 127.0)
            opp_c = quantize_ste(opp_c, 127.0, 0.0, 127.0)

        acc = torch.cat([turn_c, opp_c], dim=1) # (B, 512)

        # 2. FC1 Dense Layer with SCReLU
        z1 = torch.nn.functional.linear(acc, fc1_w, fc1_b) # (B, 64)
        c1 = torch.clamp(z1, 0.0, 1.0)
        if qat:
            c1 = quantize_ste(c1, 127.0, 0.0, 127.0)

        # Half linear, half quadratic SCReLU
        half_dim = self.mlp_dim // 2
        h_lin = c1[:, :half_dim]
        h_sq = c1[:, half_dim:] ** 2
        if qat:
            h_sq = quantize_ste(h_sq, 127.0, 0.0, 127.0)

        h = torch.cat([h_lin, h_sq], dim=1) # (B, 64)

        # 3. 8 Material / Piece-Count Output Buckets
        # <=6:0, 7-10:1, 11-14:2, 15-18:3, 19-22:4, 23-26:5, 27-29:6, >=30:7
        n_pieces = (turn_idx != 768).sum(dim=1)
        bucket = torch.zeros_like(n_pieces)
        bucket = torch.where(n_pieces > 6, torch.ones_like(bucket), bucket)
        bucket = torch.where(n_pieces > 10, torch.full_like(bucket, 2), bucket)
        bucket = torch.where(n_pieces > 14, torch.full_like(bucket, 3), bucket)
        bucket = torch.where(n_pieces > 18, torch.full_like(bucket, 4), bucket)
        bucket = torch.where(n_pieces > 22, torch.full_like(bucket, 5), bucket)
        bucket = torch.where(n_pieces > 26, torch.full_like(bucket, 6), bucket)
        bucket = torch.where(n_pieces > 29, torch.full_like(bucket, 7), bucket)

        # Gather per-sample bucket weights
        w_b = fc2_w[bucket] # (B, 64)
        b_b = fc2_b[bucket] # (B,)

        out = (h * w_b).sum(dim=1, keepdim=True) + b_b.unsqueeze(1)
        return out


def export_quantized_weights(state_dict, output_dir="weights/v2_mlp"):
    os.makedirs(output_dir, exist_ok=True)
    print("\n[Quantization] Exporting quantized INT8/INT16 weights for Numba engine...")

    w_acc = torch.round(state_dict["embedding.weight"][:768] * 127.0).to(torch.int16).cpu().numpy()
    b_acc = torch.round(state_dict["bias"] * 127.0).to(torch.int16).cpu().numpy()
    
    w_fc1 = torch.round(state_dict["fc1.weight"] * 64.0).to(torch.int8).cpu().numpy()
    b_fc1 = torch.round(state_dict["fc1.bias"] * (64.0 * 127.0)).to(torch.int32).cpu().numpy()
    
    w_fc2 = torch.round(state_dict["fc2_w"] * 87.538).to(torch.int8).cpu().numpy()
    b_fc2 = torch.round(state_dict["fc2_b"] * (87.538 * 127.0)).to(torch.int32).cpu().numpy()
    
    np.save(f"{output_dir}/weights_acc.npy", w_acc)
    np.save(f"{output_dir}/biases_acc.npy", b_acc)
    np.save(f"{output_dir}/weights_fc1.npy", w_fc1)
    np.save(f"{output_dir}/biases_fc1.npy", b_fc1)
    np.save(f"{output_dir}/weights_fc2.npy", w_fc2)
    np.save(f"{output_dir}/biases_fc2.npy", b_fc2)

    # Also save to root weights/ for backwards compatibility
    np.save("weights/weights_acc.npy", w_acc)
    np.save("weights/biases_acc.npy", b_acc)
    np.save("weights/weights_fc1.npy", w_fc1)
    np.save("weights/biases_fc1.npy", b_fc1)
    np.save("weights/weights_fc2.npy", w_fc2)
    np.save("weights/biases_fc2.npy", b_fc2)
    
    print(f"  --> Saved quantized weights to {output_dir}/ and weights/")


def train_large_dataset(shards_dir="data/shards_50m", epochs=5, batch_size=16384, lr=0.003):
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print("==================================================================")
    print("  NNUE v2 SILICON: 50M POSITIONS, 8 BUCKETS, SCReLU (QAT)        ")
    print(f"  Device: {device} | Epochs: {epochs} | Batch Size: {batch_size:,} ")
    print("==================================================================")

    shard_files = sorted(glob.glob(os.path.join(shards_dir, "shard_*.npz")))
    if not shard_files:
        raise FileNotFoundError(f"No shard files found in {shards_dir}!")

    print(f"Found {len(shard_files)} shards in {shards_dir}")

    # Load validation set from shard 0 (first 100k positions)
    print("Loading fixed validation set (100,000 positions)...")
    d0 = np.load(shard_files[0])
    val_turn_np = np.where(d0["turn_indices"][:100_000] == -1, 768, d0["turn_indices"][:100_000]).astype(np.int64)
    val_opp_np = np.where(d0["opp_indices"][:100_000] == -1, 768, d0["opp_indices"][:100_000]).astype(np.int64)
    val_target_np = d0["targets"][:100_000]

    val_turn = torch.from_numpy(val_turn_np).to(device)
    val_opp = torch.from_numpy(val_opp_np).to(device)
    val_target = torch.from_numpy(val_target_np).unsqueeze(1).to(device)
    del d0

    model = PieceSquareNNUE_V2Silicon(hidden_dim=256, mlp_dim=64, num_buckets=8).to(device)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    best_val_loss = float("inf")
    total_start = time.time()
    total_positions_seen = 0

    for epoch in range(1, epochs + 1):
        epoch_start = time.time()
        model.train()
        epoch_loss_sum = 0.0
        epoch_pos_count = 0

        print(f"\n--- [Epoch {epoch:02d}/{epochs:02d}] LR: {scheduler.get_last_lr()[0]:.6f} ---")

        for shard_idx, shard_path in enumerate(shard_files):
            t_shard = time.time()
            data = np.load(shard_path)
            t_idx = data["turn_indices"]
            o_idx = data["opp_indices"]
            tgts = data["targets"]

            # If shard 0, skip validation slice
            if shard_idx == 0:
                t_idx = t_idx[100_000:]
                o_idx = o_idx[100_000:]
                tgts = tgts[100_000:]

            t_idx = np.where(t_idx == -1, 768, t_idx).astype(np.int64)
            o_idx = np.where(o_idx == -1, 768, o_idx).astype(np.int64)

            n_shard = len(tgts)
            perm = np.random.permutation(n_shard)
            t_idx = t_idx[perm]
            o_idx = o_idx[perm]
            tgts = tgts[perm]
            del perm
            steps = math.ceil(n_shard / batch_size)

            for step in range(steps):
                s_i = step * batch_size
                e_i = min(s_i + batch_size, n_shard)

                b_turn = torch.from_numpy(t_idx[s_i:e_i]).to(device)
                b_opp = torch.from_numpy(o_idx[s_i:e_i]).to(device)
                b_tgt = torch.from_numpy(tgts[s_i:e_i]).unsqueeze(1).to(device)

                optimizer.zero_grad()
                pred = model(b_turn, b_opp, qat=True)
                loss = criterion(pred, b_tgt)
                loss.backward()
                optimizer.step()

                bs = e_i - s_i
                epoch_loss_sum += loss.item() * bs
                epoch_pos_count += bs
                total_positions_seen += bs

            del data
            shard_dur = time.time() - t_shard
            pos_per_sec = n_shard / (shard_dur + 1e-6)
            print(f"  Shard {shard_idx+1:02d}/{len(shard_files)} done in {shard_dur:4.1f}s ({pos_per_sec:,.0f} pos/s)", flush=True)

        scheduler.step()
        train_loss = epoch_loss_sum / epoch_pos_count

        # Validation
        model.eval()
        with torch.no_grad():
            val_preds = []
            v_steps = math.ceil(len(val_target) / batch_size)
            for v_s in range(v_steps):
                v_start = v_s * batch_size
                v_end = min(v_start + batch_size, len(val_target))
                pred_v = model(val_turn[v_start:v_end], val_opp[v_start:v_end], qat=False)
                val_preds.append(pred_v)
            val_preds = torch.cat(val_preds, dim=0)
            val_loss = criterion(val_preds, val_target).item()

            pred_prob = torch.sigmoid(val_preds)
            eps = 1e-6
            p_clamped = torch.clamp(val_target, eps, 1.0 - eps)
            pred_cp = val_preds * 173.71779
            tgt_cp = -400.0 * torch.log10(1.0 / p_clamped - 1.0)
            mae_cp = torch.mean(torch.abs(pred_cp - tgt_cp)).item()

        epoch_dur = time.time() - epoch_start
        print(f">> [Epoch {epoch:02d} Summary] Dur: {epoch_dur:4.1f}s | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Val MAE: {mae_cp:.1f} cp")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            print(f"  --> [NEW BEST MODEL] Saving checkpoint (Val Loss: {val_loss:.5f})...")
            torch.save(model.state_dict(), "weights/v2_mlp/checkpoint_best.pt")

    print(f"\nTraining completed in {(time.time() - total_start)/60:.1f} minutes!")
    print(f"Total positions processed: {total_positions_seen:,}")

    # Load best checkpoint and export
    print("\nLoading best model checkpoint for export...")
    best_weights = torch.load("weights/v2_mlp/checkpoint_best.pt", map_location="cpu")
    export_quantized_weights(best_weights)

if __name__ == "__main__":
    train_large_dataset(epochs=5, batch_size=16384, lr=0.003)
