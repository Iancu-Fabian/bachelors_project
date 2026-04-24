import subprocess
import time
import os
import threading
from pathlib import Path

PATTERNS = ["constant", "ramp", "spike", "wave"]
ITERATIONS = 5  
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


def collect_metrics_continuously(stop_event, interval=30):
    while not stop_event.is_set():
        print("--- Collecting Metrics ---")
        subprocess.run(["python", METRICS_SCRIPT])
        stop_event.wait(timeout=interval)


def run_locust_with_collection(pattern, duration_seconds):
    print(f"--- Starting Pattern: {pattern} for {duration_seconds}s ---")

    stop_event = threading.Event()
    collector = threading.Thread(
        target=collect_metrics_continuously,
        args=(stop_event, 30),
        daemon=True
    )
    collector.start()

    env = os.environ.copy()
    env["LOAD_PATTERN"] = pattern
    env["TARGET_HOST"] = TARGET_URL
    env["MAX_USERS"] = "3"

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


try:
    for i in range(ITERATIONS):
        print(f"\n===== STARTING GLOBAL CYCLE {i+1}/{ITERATIONS} =====")
        for pattern in PATTERNS:
            run_locust_with_collection(pattern, 300)

            print("Cooling down for 2 minutes...")
            time.sleep(120)

except KeyboardInterrupt:
    print("Orchestration stopped by user.")