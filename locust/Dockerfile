FROM python:3.11-slim

WORKDIR /locust

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir locust

COPY locustfile.py .
COPY data ./data

EXPOSE 8089

CMD ["locust", "-f", "locustfile.py"]