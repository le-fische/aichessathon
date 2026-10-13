import math
import os
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

class PieceSquareNNUEMPS(nn.Module):
    def __init__(self, hidden_dim=256):
        super().__init__()
        self.hidden_dim = hidden_dim
        # 768 features + index 768 as padding (zero-out)
        self.embedding = nn.Embedding(769, hidden_dim, padding_idx=768)
        self.bias = nn.Parameter(torch.zeros(hidden_dim))
        self.fc2 = nn.Linear(hidden_dim * 2, 1, bias=False)
        
        # Initialize weights
        nn.init.kaiming_uniform_(self.embedding.weight[:768], a=math.sqrt(5))
        with torch.no_grad():
            self.embedding.weight[768].zero_()
            nn.init.kaiming_uniform_(self.fc2.weight, a=math.sqrt(5))

    def forward(self, turn_idx, opp_idx):
        # turn_idx, opp_idx: (B, 32)
        turn_acc = self.embedding(turn_idx).sum(dim=1) + self.bias
        opp_acc = self.embedding(opp_idx).sum(dim=1) + self.bias
        
        turn_clamped = torch.clamp(turn_acc, 0.0, 1.0)
        opp_clamped = torch.clamp(opp_acc, 0.0, 1.0)
        
        acc = torch.cat([turn_clamped, opp_clamped], dim=1)
        return self.fc2(acc)

def load_data(data_path="data/packed_dataset.npz"):
    print(f"Loading packed dataset from {data_path}...")
    t0 = time.time()
    data = np.load(data_path)
    turn_indices = data["turn_indices"]
    opp_indices = data["opp_indices"]
    targets = data["targets"]
    print(f"Loaded {len(targets):,} positions in {time.time()-t0:.2f}s.")
    
    # Replace padding -1 with 768
    turn_indices = np.where(turn_indices == -1, 768, turn_indices).astype(np.int64)
    opp_indices = np.where(opp_indices == -1, 768, opp_indices).astype(np.int64)
    
    return turn_indices, opp_indices, targets

def train():
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using compute device: {device}")
    
    turn_indices, opp_indices, targets = load_data()
    n_total = len(targets)
    
    # 90/10 train/val split
    np.random.seed(42)
    indices = np.random.permutation(n_total)
    n_val = int(n_total * 0.1)
    val_idx = indices[:n_val]
    train_idx = indices[n_val:]
    
    print(f"Train set: {len(train_idx):,} positions | Val set: {len(val_idx):,} positions")
    
    # Pre-convert validation set to torch tensors on device
    val_turn = torch.from_numpy(turn_indices[val_idx]).to(device)
    val_opp = torch.from_numpy(opp_indices[val_idx]).to(device)
    val_target = torch.from_numpy(targets[val_idx]).unsqueeze(1).to(device)
    
    # Training arrays
    train_turn_np = turn_indices[train_idx]
    train_opp_np = opp_indices[train_idx]
    train_target_np = targets[train_idx]
    
    model = PieceSquareNNUEMPS(hidden_dim=256).to(device)
    criterion = nn.BCEWithLogitsLoss()
    
    lr = 0.003
    epochs = 25
    batch_size = 8192
    n_train = len(train_idx)
    steps_per_epoch = math.ceil(n_train / batch_size)
    
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    
    best_val_loss = float("inf")
    best_weights = None
    
    print(f"\nStarting training for {epochs} epochs (Batch size: {batch_size}, {steps_per_epoch} steps/epoch)...")
    total_start = time.time()
    
    for epoch in range(1, epochs + 1):
        t_epoch_start = time.time()
        model.train()
        
        # Shuffle training set each epoch
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
        
        # Validation
        model.eval()
        with torch.no_grad():
            val_pred = model(val_turn, val_opp)
            val_loss = criterion(val_pred, val_target).item()
            
            # Compute centipawn error on val set:
            # logit = pred -> sigmoid(pred) = p
            # cp = -400 * log10(1/p - 1)
            # In logits: logit = cp * ln(10) / 400 = cp / 173.71779
            # So cp = logit * 173.71779
            pred_cp = val_pred * 173.71779
            # target score in cp:
            # p = val_target -> logit_tgt = log(p / (1-p)) -> cp_tgt = logit_tgt * 173.71779
            eps = 1e-6
            p_clamped = torch.clamp(val_target, eps, 1.0 - eps)
            tgt_cp = torch.log(p_clamped / (1.0 - p_clamped)) * 173.71779
            mae_cp = torch.mean(torch.abs(pred_cp - tgt_cp)).item()
            
        epoch_time = time.time() - t_epoch_start
        print(f"Epoch {epoch:02d}/{epochs:02d} [{epoch_time:4.1f}s] "
              f"| Train Loss: {train_loss:.5f} | Val Loss: {val_loss:.5f} | Val MAE: {mae_cp:5.1f} cp | LR: {scheduler.get_last_lr()[0]:.6f}")
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            # Save state dict
            best_weights = {
                "emb": model.embedding.weight[:768].detach().cpu().clone(),
                "bias": model.bias.detach().cpu().clone(),
                "fc2": model.fc2.weight.detach().cpu().clone(),
            }
            print(f"  --> [NEW BEST] val_loss: {val_loss:.5f}")

    print(f"\nTraining completed in {time.time()-total_start:.1f}s! Best Val Loss: {best_val_loss:.5f}")
    
    # Export and Quantize
    print("\nQuantizing weights to int16/int8...")
    os.makedirs("weights", exist_ok=True)
    
    fc1_w = torch.round(best_weights["emb"] * 127.0).to(torch.int16).numpy()  # (768, 256)
    fc1_b = torch.round(best_weights["bias"] * 127.0).to(torch.int16).numpy() # (256,)
    fc2_w = torch.round(best_weights["fc2"] * 87.538).to(torch.int8).numpy()  # (1, 512)
    
    # Backup old weights
    if os.path.exists("weights/weights.npy"):
        import shutil
        shutil.copy("weights/weights.npy", "weights/weights_backup.npy")
        shutil.copy("weights/biases.npy", "weights/biases_backup.npy")
        shutil.copy("weights/weights2.npy", "weights/weights2_backup.npy")
        print("Backed up previous weights to *_backup.npy")
        
    np.save("weights/weights.npy", fc1_w) 
    np.save("weights/biases.npy", fc1_b)    
    np.save("weights/weights2.npy", fc2_w[0])  
    print("Exported weights/weights.npy, weights/biases.npy, weights/weights2.npy successfully!")

    import hashlib
    with open("weights/weights.npy", "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
        print(f"New Weights SHA256: {sha}")

if __name__ == "__main__":
    train()
