import torch
import numpy as np
import json
import os
from lstm import LSTMModel  

def model_fn(model_dir):
    device = torch.device('cpu')
    checkpoint = torch.load(
        os.path.join(model_dir, 'model.pth'),
        map_location=device
    )
    model = LSTMModel().to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    return model

def predict_fn(input_data, model):
    with torch.no_grad():
        tensor = torch.tensor(input_data, dtype=torch.float32)
        output = model(tensor)
        return output.numpy().tolist()

def input_fn(request_body, content_type='application/json'):
    data = json.loads(request_body)
    return np.array(data['inputs'])

def output_fn(prediction, accept='application/json'):
    return json.dumps({'prediction': prediction}), accept