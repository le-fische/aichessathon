import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import chess
import os
import sys
sys.path.insert(0, '.')
from evaluation import evaluate as current_evaluate

class NNUE(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(768, 256)
        self.fc2 = nn.Linear(256, 1)

    def forward(self, x):
        x = self.fc1(x)
        x = torch.clamp(x, 0, 127) # Clipped ReLU
        x = self.fc2(x)
        return x

def board_to_features(board):
    features = np.zeros(768, dtype=np.float32)
    for sq, piece in board.piece_map().items():
        color = piece.color
        pt = piece.piece_type
        c_rel = 0 if color == chess.WHITE else 1
        sq_rel = sq
        idx = c_rel * 384 + (pt - 1) * 64 + sq_rel
        features[idx] = 1.0
        
        # We also need to add black perspective? No, we said the absolute inputs.
        # Wait, the accumulator we wrote uses absolute inputs, from WHITE perspective.
        # Let's match the accumulator logic for initialization exactly:
        # white_acc uses chess.WHITE perspective.
        # So we just feed absolute pieces.
    return features

def prepare_data(npz_path):
    data = np.load(npz_path)
    fens = data['fens']
    scores = data['scores']
    
    X = []
    y = []
    
    for fen, cp in zip(fens, scores):
        board = chess.Board(fen)
        X.append(board_to_features(board))
        # CP to probability for side to move
        # but our NNUE evaluates from WHITE perspective.
        # So Stockfish score must be from WHITE perspective.
        # `score.white()` already gives WHITE perspective.
        prob = torch.sigmoid(torch.tensor(cp / 400.0)).item()
        y.append([prob])
        
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32), fens

def train():
    print("Loading labeled data...")
    X, y, fens = prepare_data("data/pilot_labeled.npz")
    
    # Validation split
    split = int(0.8 * len(X))
    X_train, y_train = X[:split], y[:split]
    X_val, y_val, val_fens = X[split:], y[split:], fens[split:]
    
    model = NNUE()
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()
    
    batch_size = 256
    epochs = 10
    
    print("Training...")
    for epoch in range(epochs):
        model.train()
        permutation = torch.randperm(X_train.size()[0])
        for i in range(0, X_train.size()[0], batch_size):
            indices = permutation[i:i+batch_size]
            batch_x, batch_y = X_train[indices], y_train[indices]
            
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(torch.sigmoid(outputs / 400.0), batch_y)
            loss.backward()
            optimizer.step()
            
        # Validation
        model.eval()
        with torch.no_grad():
            val_outputs = model(X_val)
            val_loss = criterion(torch.sigmoid(val_outputs / 400.0), y_val)
        print(f"Epoch {epoch+1}/{epochs} - Val Loss: {val_loss.item():.6f}")

    # Evaluate correlation
    model.eval()
    with torch.no_grad():
        nnue_preds = model(X_val).squeeze().numpy()
        sf_labels = (torch.logit(y_val) * 400.0).squeeze().numpy()
        
    nnue_corr = np.corrcoef(nnue_preds, sf_labels)[0, 1]
    
    # Evaluate current evaluation
    current_preds = []
    for fen in val_fens:
        board = chess.Board(fen)
        score = current_evaluate(board)
        # current_evaluate returns score for side to move, convert to white perspective
        if board.turn == chess.BLACK:
            score = -score
        current_preds.append(score)
        
    current_corr = np.corrcoef(current_preds, sf_labels)[0, 1]
    
    print(f"\nCorrelation against Stockfish:")
    print(f"Current Eval: {current_corr:.4f}")
    print(f"NNUE Model:   {nnue_corr:.4f}")
    
    # Save quantized model
    os.makedirs("weights", exist_ok=True)
    fc1_w = (model.fc1.weight.detach().numpy() * 127).astype(np.int16)
    fc1_b = (model.fc1.bias.detach().numpy() * 127).astype(np.int16)
    fc2_w = (model.fc2.weight.detach().numpy() * 127).astype(np.int16)
    fc2_b = (model.fc2.bias.detach().numpy() * 127).astype(np.int16)
    
    np.savez_compressed("weights/karpov.npz", fc1_w=fc1_w, fc1_b=fc1_b, fc2_w=fc2_w, fc2_b=fc2_b)
    print("Saved quantized weights to weights/karpov.npz")

if __name__ == "__main__":
    train()
