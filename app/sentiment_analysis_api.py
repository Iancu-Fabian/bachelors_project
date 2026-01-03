from fastapi import FastAPI
from pydantic import BaseModel
import time
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from fastapi.responses import HTMLResponse

app = FastAPI(title="Sentiment Analysis API")

class SentimentRequest(BaseModel):
    text: str
    repeat: int = 1  

class SentimentResponse(BaseModel):
    label: str
    confidence: float
    latency_ms: float


MODEL_NAME = "DGurgurov/xlm-r_romanian_sentiment"

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
model.eval()
print("Model loaded.")

id2label = model.config.id2label

@app.post("/predict", response_model=SentimentResponse)
def predict(request: SentimentRequest):
    start_time = time.time()

    with torch.no_grad():
        for _ in range(request.repeat):
            inputs = tokenizer(
                request.text,
                return_tensors="pt",
                truncation=True,
                padding=True
            )

            outputs = model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)

    confidence, predicted_class = torch.max(probs, dim=-1)
    label = "Negativ" if id2label[predicted_class.item()] == "LABEL_0" else "Pozitiv"

    latency_ms = (time.time() - start_time) * 1000

    return SentimentResponse(
        label=label,
        confidence=float(confidence.item()),
        latency_ms=latency_ms
    )

@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
      <head><title>Sentiment Analysis</title></head>
      <body>
        <h2>Sentiment Analysis</h2>
        <textarea id="text" rows="4" cols="50"></textarea><br><br>
        Repeat: <input type="number" id="repeat" value="1"><br><br>
        <button onclick="send()">Predict</button>
        <pre id="result"></pre>

        <script>
          async function send() {
            const text = document.getElementById("text").value;
            const repeat = parseInt(document.getElementById("repeat").value);

            const res = await fetch("/predict", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ text: text, repeat: repeat })
            });

            const data = await res.json();
            document.getElementById("result").innerText =
              JSON.stringify(data, null, 2);
          }
        </script>
      </body>
    </html>
    """