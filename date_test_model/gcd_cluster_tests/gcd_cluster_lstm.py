import pandas as pd
import numpy as np
import tarfile
import io
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

FILE_PATH_GZ = 'GCD_VMs.tar.gz'
LAG_STEPS = 10
TEST_SIZE_RATIO = 0.2
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
EPOCHS = 15
BATCH_SIZE = 256

all_data = []
with tarfile.open(FILE_PATH_GZ, 'r:gz') as tar:
    for member in tar.getmembers():
        if member.isfile():
            f = tar.extractfile(member)
            if f:
                df_vm = pd.read_csv(io.BytesIO(f.read()), sep=r"\s+", header=None, 
                                   names=["CPU", "Memory"], engine="python")
                all_data.append(df_vm)

df_raw = pd.concat(all_data, ignore_index=True)

scaler = StandardScaler()
scaled_data = scaler.fit_transform(df_raw[["CPU", "Memory"]])

def create_sequences(data, seq_len):
    x, y = [], []
    for i in range(len(data) - seq_len):
        x.append(data[i:i+seq_len])
        y.append(data[i+seq_len, 0]) 
    return np.array(x), np.array(y)

X, y = create_sequences(scaled_data, LAG_STEPS)

split_idx = int(len(X) * (1 - TEST_SIZE_RATIO))
x_train, x_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]

class GCDDataset(Dataset):
    def __init__(self, x, y):
        self.x = torch.tensor(x, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32).unsqueeze(-1)
    
    def __len__(self):
        return len(self.x)
    
    def __getitem__(self, idx):
        return self.x[idx], self.y[idx]

train_dataset = GCDDataset(x_train, y_train)
test_dataset = GCDDataset(x_test, y_test)

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

class LSTMModel(nn.Module):
    def __init__(self, input_dim=2, hidden_dim=64, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_dim, hidden_size=hidden_dim, 
                            num_layers=num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

def train(model, loader, optimizer, loss_fn, device):
    model.train()
    total_loss = 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        out = model(x)
        loss = loss_fn(out, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * x.size(0)
    return total_loss / len(loader.dataset)

def evaluate(model, loader, device, scaler):
    model.eval()
    all_preds = []
    all_targets = []
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            all_preds.append(out.cpu().numpy())
            all_targets.append(y.cpu().numpy())
    
    preds = np.concatenate(all_preds).flatten()
    targets = np.concatenate(all_targets).flatten()
    

    cpu_mean, cpu_std = scaler.mean_[0], scaler.scale_[0]
    preds = np.clip(preds * cpu_std + cpu_mean, 0, 100)
    targets = targets * cpu_std + cpu_mean
    
    return targets, preds

model = LSTMModel().to(DEVICE)
loss_fn = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

for epoch in range(EPOCHS):
    train_loss = train(model, train_loader, optimizer, loss_fn, DEVICE)
    print(f"Epoch {epoch+1}/{EPOCHS} - Loss: {train_loss:.4f}")

y_true, y_pred = evaluate(model, test_loader, DEVICE, scaler)

print("\n--- LSTM Results ---")
print(f"R²:   {r2_score(y_true, y_pred):.4f}")
print(f"RMSE: {np.sqrt(mean_squared_error(y_true, y_pred)):.4f} % CPU")
print(f"MAE:  {mean_absolute_error(y_true, y_pred):.4f} % CPU")