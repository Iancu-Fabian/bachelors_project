import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import MinMaxScaler

FILE_PATH = 'TestK8sData.csv'
FEATURE_COLS = ['CPU', 'PodsNumber']
TARGET_COL = 'PodsNumber'
SEQ_LENGTH = 10
TEST_SIZE_RATIO = 0.2
EPOCHS = 80
BATCH_SIZE = 64
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else
                      "cuda" if torch.cuda.is_available() else "cpu")

df = pd.read_csv(FILE_PATH)
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df = df.set_index('Timestamp').sort_index()

data = df[FEATURE_COLS].copy()

scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(data)

target_idx = FEATURE_COLS.index(TARGET_COL)


def create_sequences(data, seq_length, target_idx):
    X, y = [], []
    for i in range(len(data) - seq_length):
        X.append(data[i:i + seq_length])
        y.append(data[i + seq_length, target_idx])
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


train_loader = DataLoader(K8sDataset(X_train, y_train), batch_size=BATCH_SIZE, shuffle=False)  # ← Fixed!
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

print("Epoch   | Train Loss | RMSE    | MAE     | R²")
print("-" * 48)

best_r2 = -999
best_epoch = 0

for epoch in range(EPOCHS):
    model.train()
    total_loss = 0
    for x, y in train_loader:
        x, y = x.to(DEVICE), y.to(DEVICE)
        optimizer.zero_grad()
        pred = model(x)
        loss = loss_fn(pred, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * x.size(0)

    train_loss = total_loss / len(train_loader.dataset)

    model.eval()
    preds, trues = [], []
    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(DEVICE)
            out = model(x)
            preds.append(out.cpu().numpy())
            trues.append(y.cpu().numpy())

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

    print(f"{epoch + 1:2d}/{EPOCHS}   {train_loss:.5f}   {rmse:.4f}   {mae:.4f}   {r2:.4f}")

    if r2 > best_r2:
        best_r2 = r2
        best_epoch = epoch + 1

print(f"\nBest result: epoch {best_epoch} → R² = {best_r2:.4f}")