import json
import random
import os
from locust import HttpUser, task, between, LoadTestShape

LOAD_PATTERN = os.getenv("LOAD_PATTERN", "constant")
MAX_USERS = int(os.getenv("MAX_USERS", 50))
SPAWN_RATE = int(os.getenv("SPAWN_RATE", 5))

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


class ConstantLoad(LoadTestShape):
    time_limit = 600  

    def tick(self):
        run_time = self.get_run_time()
        if run_time > self.time_limit:
            return None
        return (MAX_USERS, SPAWN_RATE)


class RampUpLoad(LoadTestShape):
    stages = [
        (120, 10),
        (240, 25),
        (360, 50),
        (480, 75),
        (600, 100),
    ]

    def tick(self):
        run_time = self.get_run_time()
        for t, users in self.stages:
            if run_time < t:
                return (users, SPAWN_RATE)
        return None

class SpikeLoad(LoadTestShape):
    def tick(self):
        run_time = self.get_run_time()

        if run_time < 120:
            return (10, SPAWN_RATE)

        if run_time < 240:
            return (MAX_USERS, SPAWN_RATE * 3)

        if run_time < 360:
            return (15, SPAWN_RATE)

        return None


class WaveLoad(LoadTestShape):
    cycle_time = 120
    max_users = MAX_USERS

    def tick(self):
        run_time = self.get_run_time()
        users = int(
            (self.max_users / 2)
            * (1 + __import__("math").sin(run_time / self.cycle_time * 3.14))
        )
        return (max(1, users), SPAWN_RATE)

if LOAD_PATTERN == "constant":
    shape = ConstantLoad()
elif LOAD_PATTERN == "ramp":
    shape = RampUpLoad()
elif LOAD_PATTERN == "spike":
    shape = SpikeLoad()
elif LOAD_PATTERN == "wave":
    shape = WaveLoad()
else:
    raise ValueError(f"Unknown LOAD_PATTERN: {LOAD_PATTERN}")
