import os
import time
import json
import requests
import logging
import numpy as np
import boto3
from datetime import datetime, timedelta
from kubernetes import client, config
from botocore.session import Session
from requests_aws4auth import AWS4Auth

INTERVAL_SECONDS  = 30
WINDOW_SIZE       = 20
STEP              = "30s"
DELTA_RPS_WINDOW  = 5

DEPLOYMENT_NAME   = os.getenv("DEPLOYMENT_NAME", "api-deployment")
NAMESPACE         = os.getenv("NAMESPACE", "default")
SAGEMAKER_ENDPOINT = os.getenv("SAGEMAKER_ENDPOINT", "lstm-autoscaler-endpoint")
AMP_WORKSPACE_ID  = os.getenv("AMP_WORKSPACE_ID")
AWS_REGION        = os.getenv("AWS_REGION", "us-east-1")
MIN_REPLICAS      = int(os.getenv("MIN_REPLICAS", "1"))
MAX_REPLICAS      = int(os.getenv("MAX_REPLICAS", "8"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

RR_QUERY = f'sum(rate(http_requests_total{{handler="/predict"}}[1m])) OR on() vector(0)'
AMP_QUERY_URL = f"https://aps-workspaces.{AWS_REGION}.amazonaws.com/workspaces/{AMP_WORKSPACE_ID}/api/v1/query_range"

sagemaker_client = boto3.client("sagemaker-runtime", region_name=AWS_REGION)
aws_session      = Session()
aws_credentials  = aws_session.get_credentials()
aws_auth         = AWS4Auth(
    refreshable_credentials=aws_credentials,
    region=AWS_REGION,
    service='aps'
)

def step_to_seconds(step: str) -> int:
    units = {"s": 1, "m": 60, "h": 3600}
    return int(step[:-1]) * units[step[-1]]

def query_amp_rr(end_time: datetime) -> list[float]:
    start_time = end_time - timedelta(seconds=WINDOW_SIZE * step_to_seconds(STEP))
    payload = {
        "query": RR_QUERY,
        "start": str(start_time.timestamp()),
        "end":   str(end_time.timestamp()),
        "step":  STEP,
    }
    try:
        response = requests.post(AMP_QUERY_URL, data=payload, auth=aws_auth)
        response.raise_for_status()
    except Exception as e:
        log.error(f"Eroare HTTP la interogarea AMP: {e}")
        return []

    results = response.json().get("data", {}).get("result", [])
    if not results:
        log.warning("Niciun rezultat din AMP pentru request_rate.")
        return []

    values = [float(v[1]) for v in results[0]["values"]]

    if len(values) < WINDOW_SIZE:
        log.warning(f"Date insuficiente: {len(values)}/{WINDOW_SIZE} puncte")
        return []

    if all(v == 0.0 for v in values):
        log.warning("Fereastra complet zero pentru request_rate — sar peste ciclu.")
        return []

    values = values[-WINDOW_SIZE:]
    log.info(f"➔ request_rate | Puncte: {len(values)} | Valori: {[round(v,4) for v in values]}")
    return values

def compute_delta_rps(rr: np.ndarray, window: int = DELTA_RPS_WINDOW) -> np.ndarray:
    """Discrete derivative of request_rate — linear regression slope over last `window` steps."""
    delta = np.zeros(len(rr))
    for i in range(window, len(rr)):
        slope = np.polyfit(range(window), rr[i-window:i], 1)[0]
        delta[i] = slope
    return delta

def build_input_window(end_time: datetime) -> np.ndarray | None:
    rr_values = query_amp_rr(end_time)
    if not rr_values:
        return None

    rr = np.array(rr_values)  # shape (WINDOW_SIZE,)
    log.info(f"➔ request_rate | Valori: {[round(v,4) for v in rr.tolist()]}")

    return rr.reshape(1, WINDOW_SIZE, 1)  # shape (1, WINDOW_SIZE, 1)

def call_sagemaker(input_window: np.ndarray) -> float | None:
    payload = json.dumps({"inputs": input_window.tolist()})
    try:
        response = sagemaker_client.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType="application/json",
            Body=payload,
        )
        result = json.loads(response["Body"].read().decode("utf-8"))
        prediction = result["prediction"]
        if isinstance(prediction, list):
            prediction = np.array(prediction).ravel()[0]
        return float(prediction)
    except Exception as e:
        log.error(f"Eroare la apelul SageMaker: {e}")
        return None

def compute_desired_replicas(predicted_replicas_raw: float) -> int:
    if predicted_replicas_raw <= 0:
        return MIN_REPLICAS
    desired = int(round(predicted_replicas_raw))
    return max(MIN_REPLICAS, min(MAX_REPLICAS, desired))

def get_current_replicas(apps_v1: client.AppsV1Api) -> int:
    deployment = apps_v1.read_namespaced_deployment(name=DEPLOYMENT_NAME, namespace=NAMESPACE)
    return deployment.status.ready_replicas or 1

def scale_deployment(apps_v1: client.AppsV1Api, desired_replicas: int) -> None:
    body = {"spec": {"replicas": desired_replicas}}
    apps_v1.patch_namespaced_deployment_scale(name=DEPLOYMENT_NAME, namespace=NAMESPACE, body=body)
    log.info(f"Deployment scalat la {desired_replicas} replici.")

def reconcile(apps_v1: client.AppsV1Api) -> None:
    now = datetime.utcnow()
    log.info("─── Ciclu nou de reconciliere ───")

    input_window = build_input_window(now)
    if input_window is None:
        log.warning("Date insuficiente, sar peste acest ciclu.")
        return

    predicted_replicas_raw = call_sagemaker(input_window)
    if predicted_replicas_raw is None:
        log.warning("Predicție indisponibilă, sar peste acest ciclu.")
        return

    log.info(f"Replici prezise de model (raw): {predicted_replicas_raw:.2f}")

    current_replicas  = get_current_replicas(apps_v1)
    desired_replicas  = compute_desired_replicas(predicted_replicas_raw)

    log.info(f"Replici curente: {current_replicas} → dorite: {desired_replicas}")

    if desired_replicas != current_replicas:
        scale_deployment(apps_v1, desired_replicas)
    else:
        log.info("Nicio modificare necesară.")

def main():
    log.info("Controller predictiv pornit.")
    log.info(f"Deployment: {DEPLOYMENT_NAME} | Namespace: {NAMESPACE}")
    log.info(f"Window size: {WINDOW_SIZE} | Interval: {INTERVAL_SECONDS}s | Delta window: {DELTA_RPS_WINDOW}")
    log.info(f"Limiti replici: MIN={MIN_REPLICAS} / MAX={MAX_REPLICAS}")

    try:
        config.load_incluster_config()
        log.info("Kubernetes config: in-cluster")
    except config.ConfigException:
        config.load_kube_config()
        log.info("Kubernetes config: kubeconfig local")

    apps_v1 = client.AppsV1Api()

    while True:
        try:
            reconcile(apps_v1)
        except Exception as e:
            log.error(f"Eroare neașteptată în reconciliere: {e}", exc_info=True)
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()