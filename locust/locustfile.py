import json
import random
import os
from locust import FastHttpUser, task, between, LoadTestShape
import math

LOAD_PATTERN = os.getenv("LOAD_PATTERN", "constant")
MAX_USERS = int(os.getenv("MAX_USERS", 50))
SPAWN_RATE = int(os.getenv("SPAWN_RATE", 5))

print("TARGET_HOST =", os.getenv("TARGET_HOST"))

with open("data/texts.json", "r") as f:
    SAMPLE_TEXTS = json.load(f)


class SentimentUser(FastHttpUser):
    host = os.getenv("TARGET_HOST")
    wait_time = between(0.5, 2)

    # def on_start(self):
    #     self.client.keep_alive = True

    @task
    def predict_sentiment(self):
        payload = {"text": random.choice(SAMPLE_TEXTS)}

        self.client.post(
            "/predict",
            json=payload,
            headers={"Content-Type": "application/json"})
        
class EvaluationTest(LoadTestShape):
    """
    Test de evaluare de 40 minute (2400 secunde).
    Conceput special pentru a compara HPA vs LSTM.
    """
    time_limit = 2400
    spawn_rate = 3

    def tick(self):
        run_time = self.get_run_time()
        if run_time > self.time_limit:
            return None

        # 0-5 min: Baseline (Clusterul doarme la 2 replici)
        if run_time < 300: return (3, self.spawn_rate)
        
        # 5-15 min: Spike masiv și foarte brusc 
        # AICI HPA va da "SLO violations" și "Errors" din cauza Cold Start-ului.
        # LSTM ar trebui să prezică și să scaleze ÎNAINTE ca userii să atace complet.
        if run_time < 900: return (16, self.spawn_rate * 5)
        
        # 15-25 min: Platou susținut
        # Măsurăm "Area under replicas" și "Stabilization time"
        if run_time < 1500: return (14, self.spawn_rate)
        
        # 25-35 min: Drop instantaneu la trafic
        # AICI HPA va ține replicile sus degeaba timp de 5 minute (risipă de bani).
        # LSTM ar trebui să facă "Scale down" mult mai rapid.
        if run_time < 2100: return (3, self.spawn_rate)
        
        # 35-40 min: Cooldown
        return (2, self.spawn_rate)
        
class FullTest(LoadTestShape):
    time_limit = 28800
    spawn_rate = 2

    def tick(self):
        run_time = self.get_run_time()
        if run_time > self.time_limit:
            return None

        # Faza 1 (0-3600s) — Constant scăzut, 1-2 replici
        # Am urcat minimul de la 1 la 2, pentru a nu avea un trafic absolut "mort"
        if run_time < 3600:
            return (2, self.spawn_rate)

        # Faza 2 (3600-9000s) — Ramp up treptat
        # Scalat în jos: maximul atins aici este 14 (confortabil pentru cluster)
        elif run_time < 9000:
            local_time = run_time - 3600
            if local_time < 900:  return (3, self.spawn_rate)
            if local_time < 1800: return (5, self.spawn_rate)
            if local_time < 2700: return (8, self.spawn_rate)
            if local_time < 3600: return (10, self.spawn_rate)
            if local_time < 4500: return (12, self.spawn_rate)
            return (15, self.spawn_rate)

        # Faza 3 (9000-14400s) — Wave Organic (Crucial pentru LSTM)
        # Am adăugat "zgomot": o undă principală combinată cu una secundară mai mică.
        # Aceasta sparge perfecțiunea matematică a sinusului, arătând LSTM-ului un trafic mai realist.
        elif run_time < 14400:
            local_time = run_time - 9000
            cycle_time = 1200
            base_users = 8
            
            main_wave = 5 * math.sin(local_time / cycle_time * 2 * math.pi)
            noise_wave = 1.5 * math.sin(local_time / 300 * 2 * math.pi) # fluctuații mici
            
            users = int(base_users + main_wave + noise_wave)
            return (max(2, users), self.spawn_rate)

        # Faza 4 (14400-19800s) — Spike-uri calibrate (Fără Crash-uri)
        elif run_time < 19800:
            local_time = run_time - 14400
            # Spike 1: Vârf de 15 useri, rată foarte abruptă de urcare (simulează șocul)
            if 1200 < local_time < 1800:  return (15, self.spawn_rate * 4)
            # Scădere la trafic minim, învățăm modelul să elibereze rapid resursele
            if 1800 <= local_time < 3000: return (3, self.spawn_rate)
            # Spike 2: Vârful absolut al testului (18 useri). Aproape de limita de crash, dar sub ea.
            if 3000 <= local_time < 3600: return (18, self.spawn_rate * 5)
            return (5, self.spawn_rate)

        # Faza 5 (19800-25200s) — Ramp down natural
        # Coborâre asimetrică față de urcare, pentru o mai bună generalizare
        elif run_time < 25200:
            local_time = run_time - 19800
            if local_time < 900:  return (14, self.spawn_rate)
            if local_time < 1800: return (12, self.spawn_rate)
            if local_time < 2700: return (8, self.spawn_rate)
            if local_time < 3600: return (6, self.spawn_rate)
            if local_time < 4500: return (4, self.spawn_rate)
            return (2, self.spawn_rate)

        # Faza 6 (25200-28800s) — Constant scăzut final
        else:
            return (2, self.spawn_rate)
        
# class SpikeOnlyTest(LoadTestShape):
#     """
#     Test provizoriu de 90 de minute (5400 secunde) care izolează
#     comportamentul de șoc asupra clusterului.
#     """
#     time_limit = 5400
#     spawn_rate = 2

#     def tick(self):
#         run_time = self.get_run_time()
#         if run_time > self.time_limit:
#             return None

#         # 0 - 15 minute (0 - 900s): Trafic de bază, clusterul se stabilizează
#         if run_time < 900:
#             return (5, self.spawn_rate)
        
#         # 15 - 25 minute (900 - 1500s): Primul șoc (15 useri)
#         # Rată de spawn accelerată pentru a lovi clusterul brusc
#         elif run_time < 1500:
#             return (15, self.spawn_rate * 4)
        
#         # 25 - 45 minute (1500 - 2700s): Cădere bruscă la trafic minim
#         # Testăm capacitatea HPA/LSTM de a elibera rapid resursele
#         elif run_time < 2700:
#             return (3, self.spawn_rate)
        
#         # 45 - 60 minute (2700 - 3600s): Spike-ul extrem (18 useri)
#         # Acesta este momentul de stres maxim care ar trebui să activeze ~9 replici
#         elif run_time < 3600:
#             return (18, self.spawn_rate * 5)
        
#         # 60 - 90 minute (3600 - 5400s): Revenire la trafic normal și cooldown
#         else:
#             return (5, self.spawn_rate)
        
# class AmplitudeTest(LoadTestShape):
#     time_limit = 300

#     def tick(self):
#         run_time = self.get_run_time()
#         if run_time > self.time_limit:
#             return None
#         return (18, 10)

# class ConstantLoad(LoadTestShape):
#     time_limit = 600  

#     def tick(self):
#         run_time = self.get_run_time()
#         if run_time > self.time_limit:
#             return None
#         return (MAX_USERS, SPAWN_RATE)


# class RampUpLoad(LoadTestShape):
#     stages = [
#         (120, 10),
#         (240, 25),
#         (360, 50),
#         (480, 75),
#         (600, 100),
#     ]

#     def tick(self):
#         run_time = self.get_run_time()
#         for t, users in self.stages:
#             if run_time < t:
#                 return (users, SPAWN_RATE)
#         return None

# class SpikeLoad(LoadTestShape):
#     def tick(self):
#         run_time = self.get_run_time()

#         if run_time < 120:
#             return (10, SPAWN_RATE)

#         if run_time < 240:
#             return (MAX_USERS, SPAWN_RATE * 3)

#         if run_time < 360:
#             return (15, SPAWN_RATE)

#         return None


# class WaveLoad(LoadTestShape):
#     cycle_time = 120
#     max_users = MAX_USERS

#     def tick(self):
#         run_time = self.get_run_time()
#         users = int(
#             (self.max_users / 2)
#             * (1 + __import__("math").sin(run_time / self.cycle_time * 3.14))
#         )
#         return (max(1, users), SPAWN_RATE)
    
# class LowConstantLoad(LoadTestShape):
#     """Trafic constant scăzut - generează exemple cu 1-3 replici"""
#     time_limit = 600

#     def tick(self):
#         run_time = self.get_run_time()
#         if run_time > self.time_limit:
#             return None
#         return (5, 2)  # 5 useri, spawn rate mic


# class StepLoad(LoadTestShape):
#     """
#     Creștere în trepte cu pauze lungi la fiecare nivel.
#     Generează exemple echilibrate la fiecare nivel de replici.
#     """
#     stages = [
#         (150, 5),    # 1-2 replici
#         (300, 15),   # 3-4 replici
#         (450, 30),   # 5-6 replici
#         (600, 50),   # 7-8 replici
#         (700, 10),   # revenire la scăzut
#         (850, 5),
#     ]

#     def tick(self):
#         run_time = self.get_run_time()
#         for t, users in self.stages:
#             if run_time < t:
#                 return (users, 3)
#         return None


# class DoubleSpike(LoadTestShape):
#     """
#     Două spike-uri consecutive cu scădere între ele.
#     Testează generalizarea pe tipare nevăzute la antrenare.
#     """
#     def tick(self):
#         run_time = self.get_run_time()

#         if run_time < 100:
#             return (5, SPAWN_RATE)
#         if run_time < 160:
#             return (MAX_USERS, SPAWN_RATE * 3)
#         if run_time < 260:
#             return (8, SPAWN_RATE)
#         if run_time < 320:
#             return (MAX_USERS, SPAWN_RATE * 3)
#         if run_time < 420:
#             return (5, SPAWN_RATE)
#         return None


# class RampDownLoad(LoadTestShape):
#     """
#     Pornește de la trafic ridicat și scade gradual.
#     Modelul tău actual a văzut mai ales ramp-up, nu ramp-down.
#     """
#     stages = [
#         (120, 100),
#         (240, 75),
#         (360, 50),
#         (480, 25),
#         (600, 10),
#         (700, 5),
#     ]

#     def tick(self):
#         run_time = self.get_run_time()
#         for t, users in self.stages:
#             if run_time < t:
#                 return (users, SPAWN_RATE)
#         return None


# class MorningTrafficLoad(LoadTestShape):
#     """
#     Simulează trafic real de tip business hours:
#     creștere dimineața, platou ziua, scădere seara.
#     Argument puternic pentru profesori că datele sunt realiste.
#     """
#     stages = [
#         (100, 5),    # noapte - trafic minim
#         (200, 20),   # dimineață - creștere
#         (350, 60),   # zi - platou ridicat
#         (500, 40),   # după-amiază - ușoară scădere
#         (600, 15),   # seară - scădere
#         (700, 5),    # noapte - revenire la minim
#     ]

#     def tick(self):
#         run_time = self.get_run_time()
#         for t, users in self.stages:
#             if run_time < t:
#                 return (users, 3)
#         return None
    




# if LOAD_PATTERN == "constant":
#     shape = ConstantLoad()
# elif LOAD_PATTERN == "ramp":
#     shape = RampUpLoad()
# elif LOAD_PATTERN == "spike":
#     shape = SpikeLoad()
# elif LOAD_PATTERN == "wave":
#     shape = WaveLoad()
# elif LOAD_PATTERN == "low_constant":
#     shape = LowConstantLoad()
# elif LOAD_PATTERN == "step":
#     shape = StepLoad()
# elif LOAD_PATTERN == "double_spike":
#     shape = DoubleSpike()
# elif LOAD_PATTERN == "ramp_down":
#     shape = RampDownLoad()
# elif LOAD_PATTERN == "morning_traffic":
#     shape = MorningTrafficLoad()
# elif LOAD_PATTERN == "full_test":
#     shape = FullTest()
# elif LOAD_PATTERN == "amp_test":
#     shape = AmplitudeTest()

# else:
#     raise ValueError(f"Unknown LOAD_PATTERN: {LOAD_PATTERN}")

if LOAD_PATTERN == "eval_test":
    shape = EvaluationTest()
else:
    shape = FullTest()
