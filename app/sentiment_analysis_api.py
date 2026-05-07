from fastapi import FastAPI
from pydantic import BaseModel
import time
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from fastapi.responses import HTMLResponse
from prometheus_fastapi_instrumentator import Instrumentator
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Sentiment Analysis API")

Instrumentator().instrument(app).expose(app)

class SentimentRequest(BaseModel):
    text: str

class SentimentResponse(BaseModel):
    label: str
    confidence: float
    latency_ms: float


MODEL_NAME = "DGurgurov/xlm-r_romanian_sentiment"

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir="/models")
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, cache_dir="/models")
model.eval()
print("Model loaded.")

id2label = model.config.id2label
executor = ThreadPoolExecutor(max_workers=4)


def run_inference(text: str) -> dict:
    with torch.no_grad():
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True
        )
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)

    confidence, predicted_class = torch.max(probs, dim=-1)
    label = "Negativ" if id2label[predicted_class.item()] == "LABEL_0" else "Pozitiv"
    return {
        "label": label,
        "confidence": float(confidence.item())
    }


@app.post("/predict", response_model=SentimentResponse)
async def predict(request: SentimentRequest):
    start_time = time.time()

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_inference, request.text)

    latency_ms = (time.time() - start_time) * 1000

    return SentimentResponse(
        label=result["label"],
        confidence=result["confidence"],
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
        <button onclick="send()">Predict</button>
        <pre id="result"></pre>

        <script>
          async function send() {
            const text = document.getElementById("text").value;

            const res = await fetch("/predict", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ text: text })
            });

            const data = await res.json();
            document.getElementById("result").innerText =
              JSON.stringify(data, null, 2);
          }
        </script>
      </body>
    </html>
    """


@app.get("/health")
def health_check():
    return {"status": "healthy"}