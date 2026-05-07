FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1

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

CMD ["gunicorn", "sentiment_analysis_api:app", \
     "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--backlog", "50"]