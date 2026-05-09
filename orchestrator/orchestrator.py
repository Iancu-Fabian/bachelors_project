import subprocess
import time
import os
import threading
from pathlib import Path

MODE = "lstm_eval"

PATTERN_CONFIG = [
    ("eval_test", 2400, 1),
]

METRICS_SCRIPT = "metrics_exporter/exporter.py"
ORCHESTRATOR_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = ORCHESTRATOR_DIR.parent
LOCUST_PATH = "/Library/Frameworks/Python.framework/Versions/3.12/bin/locust"

def get_elb_hostname(service_name, namespace="default"):
    result = subprocess.check_output([
        "kubectl", "get", "svc", service_name,
        "-n", namespace,
        "-o", "jsonpath={.status.loadBalancer.ingress[0].hostname}"
    ])
    return result.decode().strip()

TARGET_URL = f"http://{get_elb_hostname('api-service')}"
print(TARGET_URL)

def collect_metrics_continuously(stop_event, session_id, interval=30):
    env = os.environ.copy()
    env["SESSION_ID"] = session_id
    env["MODE"] = MODE
    while not stop_event.is_set():
        print(f"--- Collecting Metrics [{MODE}] ---")
        subprocess.run(["python", METRICS_SCRIPT], env=env)
        stop_event.wait(timeout=interval)

def run_locust_with_collection(pattern, duration_seconds, session_id):
    print(f"--- Starting Pattern: {pattern} for {duration_seconds}s ---")

    stop_event = threading.Event()
    collector = threading.Thread(
        target=collect_metrics_continuously,
        args=(stop_event, session_id, 30),
        daemon=True
    )
    collector.start()

    env = os.environ.copy()
    env["LOAD_PATTERN"] = pattern
    env["TARGET_HOST"] = TARGET_URL
    env["SESSION_ID"] = session_id

    cmd = [
        LOCUST_PATH,
        "-f", "locustfile.py",
        "--headless",
        "--run-time", f"{duration_seconds}s"
    ]

    process = subprocess.Popen(cmd, env=env, cwd=str(PROJECT_ROOT / "locust"))
    process.wait()

    stop_event.set()
    collector.join()
    print(f"--- Pattern {pattern} Finished ---")

def estimate_total_time():
    total = sum(
        duration * runs + 120 * runs
        for _, duration, runs in PATTERN_CONFIG
    )
    hours = total // 3600
    minutes = (total % 3600) // 60
    return f"{hours}h {minutes}min"

try:
    print(f"Timp estimat total: {estimate_total_time()}")
    print(f"Patterns configurate: {len(PATTERN_CONFIG)}\n")

    for pattern, duration, runs in PATTERN_CONFIG:
        for i in range(runs):
            session_id = f"{pattern}_{i}_{int(time.time())}"
            print(f"\n===== {pattern.upper()} — rulare {i+1}/{runs} | session: {session_id} =====")
            run_locust_with_collection(pattern, duration, session_id)

            if i < runs - 1:
                print("Cooling down 2 minute...")
                time.sleep(120)

        print(f"Cooldown 3 minute înainte de următorul pattern...")
        time.sleep(180)

except KeyboardInterrupt:
    print("Orchestration stopped by user.")