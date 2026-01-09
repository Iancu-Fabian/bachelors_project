import json
import random
import os
from locust import HttpUser, task, between

with open("data/texts.json", "r") as f:
    SAMPLE_TEXTS = json.load(f)

class SentimentUser(HttpUser):
    wait_time = between(1, 3)

    host = os.getenv("TARGET_HOST")

    @task
    def predict_sentiment(self):
        payload = {"text": random.choice(SAMPLE_TEXTS)}

        self.client.post(
            "/predict",
            json=payload,
            headers={"Content-Type": "application/json"}
        )