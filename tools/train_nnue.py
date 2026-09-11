import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import chess
import sys
import glob

class ChessDataset(Dataset):
    def __init__(self, shards_pattern):
        self.fens = []
        self.scores = []
        files = glob.glob(shards_pattern)
        print(f"Loading {len(files)} shards...")
        for csv_file in files:
            with open(csv_file, "r") as f:
                lines = f.readlines()[1:]
                for line in lines:
                    parts = line.strip().rsplit(',', 1)
                    if len(parts) == 2:
                        self.fens.append(parts[0])
                        self.scores.append(float(parts[1]))
        print(f"Loaded {len(self.fens)} positions total.")
                    
    def __len__(self):
        return len(self.fens)
        
    def __getitem__(self, idx):
        fen = self.fens[idx]
        score = self.scores[idx]
        
        board = chess.Board(fen)
        turn = board.turn
        
        w_feat = np.zeros(768, dtype=np.float32)
        b_feat = np.zeros(768, dtype=np.float32)
        
        for sq, piece in board.piece_map().items():
            pt = piece.piece_type - 1 
            c = 0 if piece.color == chess.WHITE else 1
            
            w_idx = c * 384 + pt * 64 + sq
            w_feat[w_idx] = 1.0
            
            b_idx = (c ^ 1) * 384 + pt * 64 + (sq ^ 56)
            b_feat[b_idx] = 1.0
            
        target = 1.0 / (1.0 + 10.0 ** (-score / 400.0))
        
        if turn == chess.WHITE:
            return torch.tensor(w_feat), torch.tensor(b_feat), torch.tensor([target], dtype=torch.float32)
        else:
            return torch.tensor(b_feat), torch.tensor(w_feat), torch.tensor([target], dtype=torch.float32)

class PieceSquareNNUE(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(768, 256)
        self.fc2 = nn.Linear(512, 1, bias=False)
        
    def forward(self, turn_feat, opp_feat):
        turn_acc = torch.clamp(self.fc1(turn_feat), 0.0, 1.0)
        opp_acc = torch.clamp(self.fc1(opp_feat), 0.0, 1.0)
        acc = torch.cat([turn_acc, opp_acc], dim=1)
        return self.fc2(acc)

def run():
    dataset = ChessDataset("data/shards/dataset_shard_*.csv")
    dataloader = DataLoader(dataset, batch_size=4096, shuffle=True, num_workers=0)
    
    model = PieceSquareNNUE()
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    
    epochs = 5
    print(f"Training for {epochs} epochs on CPU...")
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for w, b, t in dataloader:
            optimizer.zero_grad()
            out = model(w, b)
            loss = criterion(out, t)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}")
        
    print("Quantizing and exporting weights...")
    fc1_w = torch.round(model.fc1.weight.data * 127.0).to(torch.int16).numpy()
    fc1_b = torch.round(model.fc1.bias.data * 127.0).to(torch.int16).numpy()
    
    fc2_w = torch.round(model.fc2.weight.data * 87.538).to(torch.int8).numpy()
    
    np.save("weights/weights.npy", fc1_w.T) 
    np.save("weights/biases.npy", fc1_b)    
    np.save("weights/weights2.npy", fc2_w[0])  
    print("Exported weights.npy, biases.npy, weights2.npy")
    
    import hashlib
    with open("weights/weights.npy", "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
        print(f"Weights SHA256: {sha}")

if __name__ == "__main__":
    run()
