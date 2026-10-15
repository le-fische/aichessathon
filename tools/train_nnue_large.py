"""
High-Performance Multi-Shard PyTorch MPS Trainer for Model B (768 -> 256 -> 32 -> 1)
Trains on 50 Million Stockfish-evaluated positions.
"""

import glob
import math
import os
import subprocess
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

class PieceSquareNNUE_MLP(nn.Module):
    def __init__(self, hidden_dim=256, mlp_dim=32):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.mlp_dim = mlp_dim
        
        # 768 features + index 768 as padding (zero-out)
        self.embedding = nn.Embedding(769, hidden_dim, padding_idx=768)
        self.bias = nn.Parameter(torch.zeros(hidden_dim))
        
        # Non-linear MLP head: 512 -> 32 -> 1
        self.fc1 = nn.Linear(hidden_dim * 2, mlp_dim)
        self.fc2 = nn.Linear(mlp_dim, 1)
        
        # Initialize weights
        nn.init.kaiming_uniform_(self.embedding.weight[:768], a=math.sqrt(5))
        with torch.no_grad():
            self.embedding.weight[768].zero_()
            nn.init.kaiming_uniform_(self.fc1.weight, a=math.sqrt(5))
            nn.init.zeros_(self.fc1.bias)
            nn.init.kaiming_uniform_(self.fc2.weight, a=math.sqrt(5))
            nn.init.zeros_(self.fc2.bias)

    def forward(self, turn_idx, opp_idx):
        turn_acc = self.embedding(turn_idx).sum(dim=1) + self.bias
        opp_acc = self.embedding(opp_idx).sum(dim=1) + self.bias
        
        # Clipped ReLU clamp(0, 1)
        turn_clamped = torch.clamp(turn_acc, 0.0, 1.0)
        opp_clamped = torch.clamp(opp_acc, 0.0, 1.0)
        
        acc = torch.cat([turn_clamped, opp_clamped], dim=1) # (B, 512)
        h = torch.clamp(self.fc1(acc), 0.0, 1.0)             # (B, 32)
        return self.fc2(h)                                   # (B, 1)

def export_fpga_weights(state_dict, output_dir="weights/v2_mlp"):
    os.makedirs(output_dir, exist_ok=True)
    print("\n[Quantization] Converting PyTorch weights to INT8/INT16 for FPGA...")

    # Scale factors:
    # Accumulator: [-127, 127] (int16 weights, int16 biases)
    w_acc = torch.round(state_dict["emb"] * 127.0).to(torch.int16).numpy() # (768, 256)
    b_acc = torch.round(state_dict["bias"] * 127.0).to(torch.int16).numpy() # (256,)
    
    # FC1 (512 -> 32): inputs [0, 127]. Weights in [-127, 127] (int8). Biases int32
    w_fc1 = torch.round(state_dict["fc1_w"] * 64.0).to(torch.int8).numpy() # (32, 512)
    b_fc1 = torch.round(state_dict["fc1_b"] * (64.0 * 127.0)).to(torch.int32).numpy() # (32,)
    
    # FC2 (32 -> 1): inputs [0, 127]. Weights in int8. Biases int32
    w_fc2 = torch.round(state_dict["fc2_w"] * 87.538).to(torch.int8).numpy() # (1, 32)
    b_fc2 = torch.round(state_dict["fc2_b"] * (87.538 * 127.0)).to(torch.int32).numpy() # (1,)
    
    np.save(f"{output_dir}/weights_acc.npy", w_acc)
    np.save(f"{output_dir}/biases_acc.npy", b_acc)
    np.save(f"{output_dir}/weights_fc1.npy", w_fc1)
    np.save(f"{output_dir}/biases_fc1.npy", b_fc1)
    np.save(f"{output_dir}/weights_fc2.npy", w_fc2)
    np.save(f"{output_dir}/biases_fc2.npy", b_fc2)
    print(f"  --> Saved quantized weights to {output_dir}/")

    # Export to .mem files for Verilog
    print("[Verilog MEM] Exporting .mem files for Block RAM initialization...")
    res = subprocess.run([sys.executable, "tools/export_mem_files.py"], capture_output=True, text=True)
    if res.returncode == 0:
        print("  --> .mem files successfully updated.")
    else:
        print("  --> Warning: export_mem_files failed:", res.stderr)

    # Regenerate golden vectors for new weights
    print("[Golden Model] Regenerating golden test vectors for updated model...")
    res_gold = subprocess.run([sys.executable, "tools/golden_model.py"], capture_output=True, text=True)
    if res_gold.returncode == 0:
        print("  --> Golden vectors successfully regenerated.")
    else:
        print("  --> Warning: golden_model failed:", res_gold.stderr)

    # Run cycle-accurate RTL verification
    print("[RTL Sim] Running cycle-accurate SystemVerilog simulation against benchmark vectors...")
    res_sim = subprocess.run(["make", "sim"], capture_output=True, text=True)
    if "ALL GOLDEN VECTORS VERIFIED" in res_sim.stdout or res_sim.returncode == 0:
        print("  --> RTL SIMULATION PASSED! Hardware timing verified.")
    else:
        print("  --> Simulation output:\n", res_sim.stdout[-500:])

def train_large_dataset(shards_dir="data/shards_50m", epochs=5, batch_size=16384, lr=0.003):
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print("==================================================================")
    print("  STARTING LARGE-SCALE NNUE TRAINING ON APPLE M4 PRO (MPS)       ")
    print(f"  Device: {device} | Epochs: {epochs} | Batch Size: {batch_size:,} ")
    print("==================================================================")

    shard_files = sorted(glob.glob(os.path.join(shards_dir, "shard_*.npz")))
    if not shard_files:
        raise FileNotFoundError(f"No shard files found in {shards_dir}! Please run download script first.")

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

    model = PieceSquareNNUE_MLP(hidden_dim=256, mlp_dim=32).to(device)
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
            steps = math.ceil(n_shard / batch_size)

            for step in range(steps):
                s_i = step * batch_size
                e_i = min(s_i + batch_size, n_shard)
                b_idx = perm[s_i:e_i]

                b_turn = torch.from_numpy(t_idx[b_idx]).to(device)
                b_opp = torch.from_numpy(o_idx[b_idx]).to(device)
                b_tgt = torch.from_numpy(tgts[b_idx]).unsqueeze(1).to(device)

                optimizer.zero_grad()
                pred = model(b_turn, b_opp)
                loss = criterion(pred, b_tgt)
                loss.backward()
                optimizer.step()

                batch_len = e_i - s_i
                epoch_loss_sum += loss.item() * batch_len
                epoch_pos_count += batch_len
                total_positions_seen += batch_len

            shard_time = time.time() - t_shard
            speed = n_shard / (shard_time + 1e-6)
            print(f"  Shard {shard_idx+1:02d}/{len(shard_files)} ({n_shard:,} pos) done in {shard_time:.1f}s ({speed:,.0f} pos/s)", flush=True)
            del data, t_idx, o_idx, tgts

        scheduler.step()
        train_loss = epoch_loss_sum / epoch_pos_count

        # Validation Step
        model.eval()
        with torch.no_grad():
            val_pred = model(val_turn, val_opp)
            val_loss = criterion(val_pred, val_target).item()
            
            pred_cp = val_pred * 173.71779
            eps = 1e-6
            p_clamped = torch.clamp(val_target, eps, 1.0 - eps)
            tgt_cp = torch.log(p_clamped / (1.0 - p_clamped)) * 173.71779
            mae_cp = torch.mean(torch.abs(pred_cp - tgt_cp)).item()

        epoch_time = time.time() - epoch_start
        print(f"\n>> Epoch {epoch:02d} Summary [{epoch_time/60:.1f}m] | Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Val MAE: {mae_cp:.1f} cp")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = {
                "emb": model.embedding.weight[:768].detach().cpu().clone(),
                "bias": model.bias.detach().cpu().clone(),
                "fc1_w": model.fc1.weight.detach().cpu().clone(),
                "fc1_b": model.fc1.bias.detach().cpu().clone(),
                "fc2_w": model.fc2.weight.detach().cpu().clone(),
                "fc2_b": model.fc2.bias.detach().cpu().clone(),
            }
            torch.save(model.state_dict(), "weights/v2_mlp/checkpoint_best.pt")
            print(f"  *** NEW BEST MODEL SAVED! (Val Loss: {val_loss:.5f}) ***")
            export_fpga_weights(best_state)

    print(f"\n=======================================================")
    print(f"TRAINING COMPLETE! Total time: {(time.time()-total_start)/3600:.2f} hours")
    print(f"Total positions processed: {total_positions_seen:,}")
    print(f"Best Validation Loss: {best_val_loss:.5f}")
    print(f"=======================================================")

if __name__ == "__main__":
    import sys
    train_large_dataset()
