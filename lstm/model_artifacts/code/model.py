import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from sklearn.preprocessing import MinMaxScaler

FEATURE_COLS = ['request_rate', 'cpu_usage', 'latency_p95', 'replica_count']
TARGET_COL = 'replica_count'
TEST_SIZE_RATIO = 0.2
EPOCHS = 200
BATCH_SIZE = 64
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
SEQ_LENGTH = 10

df = pd.read_csv('../../dataset/training_dataset.csv', index_col=0)
df = df.sort_index()
df = df[df['memory_usage'] > 0]
df = df[~((df['cpu_usage'] == 0) & 
          (df['request_rate'] == 0) & 
          (df['replica_count'] == 0))]
df['replica_count'] = df['replica_count'].replace(0, np.nan).ffill().bfill()
df['cpu_usage'] = df['cpu_usage'].ffill()
df = df.dropna()
df = df.sort_index().reset_index()

print(f"Rows after preprocessing: {len(df)}")
print(f"\nReplica count distribution:")
print(df['replica_count'].value_counts().sort_index())
print(f"\nRows with active traffic: {len(df[df['request_rate'] > 0])}")
print(f"Idle rows: {len(df[df['request_rate'] == 0])}")

data = df[FEATURE_COLS].copy()

split_row = int(len(data) * (1 - TEST_SIZE_RATIO))

scaler = MinMaxScaler()
scaler.fit(data.iloc[:split_row])
scaled_data = scaler.transform(data)

HORIZON = 1  
target_idx = FEATURE_COLS.index(TARGET_COL)

def create_sequences(data, seq_length, target_idx, horizon=HORIZON):
    X, y = [], []
    for i in range(len(data) - seq_length - horizon):
        X.append(data[i:i + seq_length])
        y.append(data[i + seq_length + horizon, target_idx])
    return np.array(X), np.array(y)


X_seq, y_seq = create_sequences(scaled_data, SEQ_LENGTH, target_idx)

split = int(len(X_seq) * (1 - TEST_SIZE_RATIO))
X_train, X_test = X_seq[:split], X_seq[split:]
y_train, y_test = y_seq[:split], y_seq[split:]

class K8sDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32).unsqueeze(-1)

    def __len__(self): return len(self.X)

    def __getitem__(self, idx): return self.X[idx], self.y[idx]


train_loader = DataLoader(K8sDataset(X_train, y_train), batch_size=BATCH_SIZE, shuffle=True)  
test_loader = DataLoader(K8sDataset(X_test, y_test), batch_size=BATCH_SIZE, shuffle=False)

class LSTMModel(nn.Module):
    def __init__(self, input_size=len(FEATURE_COLS), hidden_size=64, num_layers=2, dropout=0.15):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                            batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

model = LSTMModel().to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=0.0008)
loss_fn = nn.MSELoss()

MODEL_SAVE_PATH = "best_lstm_model.pt"

print("Epoch   | Train Loss | Val Loss | RMSE    | MAE     | R²")
print("-" * 58)

best_val_loss = float('inf') # Inițializăm cu infinit
best_epoch = 0

for epoch in range(EPOCHS):
    model.train()
    total_train_loss = 0
    for x, y in train_loader:
        x, y = x.to(DEVICE), y.to(DEVICE)
        optimizer.zero_grad()
        pred = model(x)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()
        total_train_loss += loss.item() * x.size(0)
    train_loss = total_train_loss / len(train_loader.dataset)

    model.eval()
    total_val_loss = 0
    preds, trues = [], []
    with torch.no_grad():
        for x, y in test_loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            out = model(x)
            v_loss = loss_fn(out, y)
            total_val_loss += v_loss.item() * x.size(0)
            
            preds.append(out.cpu().numpy())
            trues.append(y.cpu().numpy())

    val_loss = total_val_loss / len(test_loader.dataset)
    
    preds = np.concatenate(preds).ravel()
    trues = np.concatenate(trues).ravel()
    
    dummy = np.zeros((len(preds), len(FEATURE_COLS)))
    dummy[:, target_idx] = preds
    pred_unscaled = scaler.inverse_transform(dummy)[:, target_idx]

    dummy[:, target_idx] = trues
    true_unscaled = scaler.inverse_transform(dummy)[:, target_idx]

    pred_final = np.round(np.clip(pred_unscaled, 0, None))
    
    rmse = np.sqrt(mean_squared_error(true_unscaled, pred_final))
    mae = mean_absolute_error(true_unscaled, pred_final)
    r2 = r2_score(true_unscaled, pred_final)

    print(f"{epoch + 1:2d}/{EPOCHS}   {train_loss:.5f}   {val_loss:.5f}   {rmse:.4f}   {mae:.4f}   {r2:.4f}")

    if val_loss < best_val_loss:
        best_val_loss = val_loss
        best_epoch = epoch + 1
        torch.save({
            'epoch': best_epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'val_loss': best_val_loss,
            'r2': r2,
            'scaler': scaler
        }, MODEL_SAVE_PATH)

print(f"\nFinalizat! Cel mai bun model a fost la epoca {best_epoch} cu Val Loss: {best_val_loss:.6f}")

