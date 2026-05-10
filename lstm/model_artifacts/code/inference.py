import torch
import numpy as np
import json
import os
from torch import nn

class LSTMModel(nn.Module):
    def __init__(self, input_size=1, hidden_size=32, dropout=0.1):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=1,
                            batch_first=True, dropout=0)
        self.fc = nn.Linear(hidden_size + 1, 1)  # +1 for skip connection

    def forward(self, x):
        out, _ = self.lstm(x)
        last_hidden = out[:, -1, :]           # final LSTM state
        current_rr  = x[:, -1, :]            # skip connection: raw current RPS
        combined    = torch.cat([last_hidden, current_rr], dim=1)
        return self.fc(combined)


def model_fn(model_dir):
    device = torch.device('cpu')
    checkpoint = torch.load(
        os.path.join(model_dir, 'model.pt'),
        map_location=device
    )

    model = LSTMModel().to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    if 'feature_scaler' not in checkpoint or 'target_scaler' not in checkpoint:
        raise ValueError("Scalers not found in checkpoint!")
        
    model.feature_scaler = checkpoint['feature_scaler']
    model.target_scaler  = checkpoint['target_scaler']
    return model

    

def predict_fn(input_data, model):
    batch_size, seq_len, num_features = input_data.shape
    input_2d  = input_data.reshape(-1, num_features)
    scaled_2d = model.feature_scaler.transform(input_2d)
    scaled_3d = scaled_2d.reshape(batch_size, seq_len, num_features)

    with torch.no_grad():
        tensor = torch.tensor(scaled_3d, dtype=torch.float32)
        output = model(tensor)
        preds  = output.numpy()

    print(f"[DEBUG] raw model output: {preds.ravel().tolist()}", flush=True)
    print(f"[DEBUG] input window last step rr={input_data[0,-1,0]:.4f}", flush=True)

    unscaled = model.target_scaler.inverse_transform(preds.reshape(-1, 1)).ravel()
    print(f"[DEBUG] unscaled prediction: {unscaled.tolist()}", flush=True)

    return np.round(np.clip(unscaled, 1, None)).astype(int).tolist()

def input_fn(request_body, content_type='application/json'):
    data = json.loads(request_body)
    return np.array(data['inputs'])

def output_fn(prediction, accept='application/json'):
    return json.dumps({'prediction': prediction}), accept