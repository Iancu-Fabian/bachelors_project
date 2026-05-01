import torch
import numpy as np
import json
import os
from torch import nn

class LSTMModel(nn.Module):
    def __init__(self, input_size=4, hidden_size=64, num_layers=2, dropout=0.15):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                            batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])
    
def model_fn(model_dir):
    device = torch.device('cpu')
    checkpoint = torch.load(
        os.path.join(model_dir, 'model.pt'),
        map_location=device
    )
    
    model = LSTMModel().to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    if 'scaler' in checkpoint:
        model.scaler = checkpoint['scaler']
    else:
        raise ValueError("Scaler not found in model checkpoint!")
        
    return model

def predict_fn(input_data, model):
    scaler = model.scaler
    batch_size, seq_len, num_features = input_data.shape
    
    input_2d = input_data.reshape(-1, num_features)
    scaled_2d = scaler.transform(input_2d)
    
    scaled_3d = scaled_2d.reshape(batch_size, seq_len, num_features)
    
    with torch.no_grad():
        tensor = torch.tensor(scaled_3d, dtype=torch.float32)
        output = model(tensor)
        preds = output.numpy() 
        
    target_idx = 3 
    dummy = np.zeros((len(preds), num_features))
    dummy[:, target_idx] = preds.ravel()
    
    unscaled_preds = scaler.inverse_transform(dummy)[:, target_idx]
    
    final_preds = np.round(np.clip(unscaled_preds, 0, None))
    
    return final_preds.tolist()

def input_fn(request_body, content_type='application/json'):
    data = json.loads(request_body)
    return np.array(data['inputs'])

def output_fn(prediction, accept='application/json'):
    return json.dumps({'prediction': prediction}), accept