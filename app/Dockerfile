FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ENV HF_HOME=/models

RUN python - <<EOF
from transformers import AutoTokenizer, AutoModelForSequenceClassification
model_name = "DGurgurov/xlm-r_romanian_sentiment"
AutoTokenizer.from_pretrained(model_name, cache_dir="/models")
AutoModelForSequenceClassification.from_pretrained(model_name, cache_dir="/models")
EOF

COPY sentiment_analysis_api.py .

EXPOSE 8000

CMD ["uvicorn", "sentiment_analysis_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]