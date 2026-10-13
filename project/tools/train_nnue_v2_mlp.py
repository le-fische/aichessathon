import math
import os
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
        
        # Clipped ReLU / clamp(0, 1)
        turn_clamped = torch.clamp(turn_acc, 0.0, 1.0)
        opp_clamped = torch.clamp(opp_acc, 0.0, 1.0)
        
        acc = torch.cat([turn_clamped, opp_clamped], dim=1) # (B, 512)
        h = torch.clamp(self.fc1(acc), 0.0, 1.0)             # (B, 32)
        return self.fc2(h)                                   # (B, 1)

def train_mlp():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using compute device: {device}")
    
    data_path = "data/packed_dataset.npz"
    print(f"Loading packed dataset from {data_path}...")
    t0 = time.time()
    data = np.load(data_path)
    turn_indices = data["turn_indices"]
    opp_indices = data["opp_indices"]
    targets = data["targets"]
    print(f"Loaded {len(targets):,} positions in {time.time()-t0:.2f}s.")
    
    turn_indices = np.where(turn_indices == -1, 768, turn_indices).astype(np.int64)
    opp_indices = np.where(opp_indices == -1, 768, opp_indices).astype(np.int64)
    
    n_total = len(targets)
    np.random.seed(42)
    indices = np.random.permutation(n_total)
    n_val = int(n_total * 0.1)
    val_idx = indices[:n_val]
    train_idx = indices[n_val:]
    
    print(f"Train set: {len(train_idx):,} positions | Val set: {len(val_idx):,} positions")
    
    val_turn = torch.from_numpy(turn_indices[val_idx]).to(device)
    val_opp = torch.from_numpy(opp_indices[val_idx]).to(device)
    val_target = torch.from_numpy(targets[val_idx]).unsqueeze(1).to(device)
    
    train_turn_np = turn_indices[train_idx]
    train_opp_np = opp_indices[train_idx]
    train_target_np = targets[train_idx]
    
    model = PieceSquareNNUE_MLP(hidden_dim=256, mlp_dim=32).to(device)
    criterion = nn.BCEWithLogitsLoss()
    
    epochs = 25
    batch_size = 8192
    n_train = len(train_idx)
    steps_per_epoch = math.ceil(n_train / batch_size)
    
    optimizer = optim.AdamW(model.parameters(), lr=0.003, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    
    best_val_loss = float("inf")
    best_state = None
    
    print(f"\nStarting training 768 -> 256 -> 32 -> 1 for {epochs} epochs...")
    total_start = time.time()
    
    for epoch in range(1, epochs + 1):
        t_epoch_start = time.time()
        model.train()
        
        perm = np.random.permutation(n_train)
        train_loss_sum = 0.0
        
        for step in range(steps_per_epoch):
            start_i = step * batch_size
            end_i = min(start_i + batch_size, n_train)
            batch_indices = perm[start_i:end_i]
            
            b_turn = torch.from_numpy(train_turn_np[batch_indices]).to(device)
            b_opp = torch.from_numpy(train_opp_np[batch_indices]).to(device)
            b_tgt = torch.from_numpy(train_target_np[batch_indices]).unsqueeze(1).to(device)
            
            optimizer.zero_grad()
            pred = model(b_turn, b_opp)
            loss = criterion(pred, b_tgt)
            loss.backward()
            optimizer.step()
            
            train_loss_sum += loss.item() * (end_i - start_i)
            
        scheduler.step()
        train_loss = train_loss_sum / n_train
        
        model.eval()
        with torch.no_grad():
            val_pred = model(val_turn, val_opp)
            val_loss = criterion(val_pred, val_target).item()
            
            pred_cp = val_pred * 173.71779
            eps = 1e-6
            p_clamped = torch.clamp(val_target, eps, 1.0 - eps)
            tgt_cp = torch.log(p_clamped / (1.0 - p_clamped)) * 173.71779
            mae_cp = torch.mean(torch.abs(pred_cp - tgt_cp)).item()
            
        epoch_time = time.time() - t_epoch_start
        print(f"Epoch {epoch:02d}/{epochs:02d} [{epoch_time:4.1f}s] "
              f"| Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Val MAE: {mae_cp:5.1f} cp | LR: {scheduler.get_last_lr()[0]:.6f}")
        
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
            print(f"  --> [NEW BEST MLP] val_loss: {val_loss:.5f}")

    print(f"\nTraining completed in {time.time()-total_start:.1f}s! Best Val Loss: {best_val_loss:.5f}")
    
    # Export MLP weights quantized for FPGA
    print("\nQuantizing weights for FPGA accelerator...")
    os.makedirs("weights/v2_mlp", exist_ok=True)
    
    # Scale factors:
    # Accumulator: [-127, 127] (int16 weights, int16 biases)
    w_acc = torch.round(best_state["emb"] * 127.0).to(torch.int16).numpy() # (768, 256)
    b_acc = torch.round(best_state["bias"] * 127.0).to(torch.int16).numpy() # (256,)
    
    # FC1 (512 -> 32): inputs are in [0, 127]. Weights in [-127, 127] (int8)
    # Output before clamp is (sum of 512 * int8 * int8) / 128
    w_fc1 = torch.round(best_state["fc1_w"] * 64.0).to(torch.int8).numpy() # (32, 512)
    b_fc1 = torch.round(best_state["fc1_b"] * (64.0 * 127.0)).to(torch.int32).numpy() # (32,)
    
    # FC2 (32 -> 1): inputs are in [0, 127]. Weights in int8.
    w_fc2 = torch.round(best_state["fc2_w"] * 87.538).to(torch.int8).numpy() # (1, 32)
    b_fc2 = torch.round(best_state["fc2_b"] * (87.538 * 127.0)).to(torch.int32).numpy() # (1,)
    
    np.save("weights/v2_mlp/weights_acc.npy", w_acc)
    np.save("weights/v2_mlp/biases_acc.npy", b_acc)
    np.save("weights/v2_mlp/weights_fc1.npy", w_fc1)
    np.save("weights/v2_mlp/biases_fc1.npy", b_fc1)
    np.save("weights/v2_mlp/weights_fc2.npy", w_fc2)
    np.save("weights/v2_mlp/biases_fc2.npy", b_fc2)
    
    print("Successfully exported quantized FPGA accelerator weights to weights/v2_mlp/!")

if __name__ == "__main__":
    train_mlp()
