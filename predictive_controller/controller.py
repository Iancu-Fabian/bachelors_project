import os
import time
import json
import logging
import numpy as np
import boto3
from datetime import datetime, timedelta
from kubernetes import client, config

INTERVAL_SECONDS      = 30
WINDOW_SIZE           = 30          
STEP                  = "30s"       

DEPLOYMENT_NAME       = os.getenv("DEPLOYMENT_NAME", "api-deployment")
NAMESPACE             = os.getenv("NAMESPACE", "default")
SAGEMAKER_ENDPOINT    = os.getenv("SAGEMAKER_ENDPOINT", "lstm-autoscaler-endpoint")
AMP_WORKSPACE_ID      = os.getenv("AMP_WORKSPACE_ID")
AWS_REGION            = os.getenv("AWS_REGION", "us-east-1")

MIN_REPLICAS          = int(os.getenv("MIN_REPLICAS", "1"))
MAX_REPLICAS          = int(os.getenv("MAX_REPLICAS", "10"))
CPU_TARGET            = float(os.getenv("CPU_TARGET", "60.0"))  

FEATURE_COLS          = ['request_rate', 'cpu_usage', 'latency_p95', 'replica_count']

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

QUERIES = {
    "request_rate": 'sum(rate(http_requests_total{namespace="' + NAMESPACE + '"}[1m]))',
    "cpu_usage":    'avg(rate(container_cpu_usage_seconds_total{namespace="' + NAMESPACE + '", container="sentiment-api"}[1m])) * 100',
    "latency_p95":  'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{namespace="' + NAMESPACE + '"}[1m])) by (le)) * 1000',
    "replica_count": 'kube_deployment_status_replicas_ready{namespace="' + NAMESPACE + '", deployment="' + DEPLOYMENT_NAME + '"}',
}

# ── Clienți AWS ───────────────────────────────────────────────────────────────
amp_client       = boto3.client("amp", region_name=AWS_REGION)
sagemaker_client = boto3.client("sagemaker-runtime", region_name=AWS_REGION)


def query_amp_range(metric_name: str, end_time: datetime) -> list[float]:
    """Interoghează AMP pentru ultimele WINDOW_SIZE puncte ale unei metrici."""
    start_time = end_time - timedelta(seconds=WINDOW_SIZE * int(STEP[:-1]))
    query      = QUERIES[metric_name]

    response = amp_client.query_range(
        workspaceId=AMP_WORKSPACE_ID,
        query=query,
        startTime=start_time.isoformat() + "Z",
        endTime=end_time.isoformat() + "Z",
        step=STEP,
    )

    results = response.get("data", {}).get("result", [])
    if not results:
        log.warning(f"Niciun rezultat din AMP pentru metrica: {metric_name}")
        return []

    values = [float(v[1]) for v in results[0]["values"]]

    if len(values) < WINDOW_SIZE:
        log.warning(f"Date insuficiente pentru {metric_name}: {len(values)}/{WINDOW_SIZE} puncte")
        return []

    return values[-WINDOW_SIZE:]


def build_input_window(end_time: datetime) -> np.ndarray | None:
    """
    Construiește fereastra de input pentru model.
    Shape: (1, WINDOW_SIZE, len(FEATURE_COLS))
    """
    window = []
    for feature in FEATURE_COLS:
        values = query_amp_range(feature, end_time)
        if not values:
            return None
        window.append(values)

    arr = np.array(window).T
    return arr.reshape(1, WINDOW_SIZE, len(FEATURE_COLS))


def call_sagemaker(input_window: np.ndarray) -> float | None:
    """Trimite fereastra către SageMaker și returnează predicția de CPU usage."""
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


def compute_desired_replicas(predicted_cpu: float, current_replicas: int) -> int:
    """
    Calculează numărul de replici necesar pe baza predicției de CPU.
    Folosește aceeași formulă ca HPA, aplicată pe valoarea prezisă.
    """
    if predicted_cpu <= 0:
        return MIN_REPLICAS

    desired = int(np.ceil(current_replicas * (predicted_cpu / CPU_TARGET)))
    desired = max(MIN_REPLICAS, min(MAX_REPLICAS, desired))
    return desired


def get_current_replicas(apps_v1: client.AppsV1Api) -> int:
    """Returnează numărul curent de replici ready ale deployment-ului."""
    deployment = apps_v1.read_namespaced_deployment(
        name=DEPLOYMENT_NAME,
        namespace=NAMESPACE
    )
    return deployment.status.ready_replicas or 1


def scale_deployment(apps_v1: client.AppsV1Api, desired_replicas: int) -> None:
    """Actualizează numărul de replici ale deployment-ului."""
    body = {"spec": {"replicas": desired_replicas}}
    apps_v1.patch_namespaced_deployment_scale(
        name=DEPLOYMENT_NAME,
        namespace=NAMESPACE,
        body=body
    )
    log.info(f"Deployment scalat la {desired_replicas} replici.")


def reconcile(apps_v1: client.AppsV1Api) -> None:
    """Un ciclu complet de reconciliere."""
    now = datetime.utcnow()
    log.info("─── Ciclu nou de reconciliere ───")

    input_window = build_input_window(now)
    if input_window is None:
        log.warning("Date insuficiente, sar peste acest ciclu.")
        return

    predicted_cpu = call_sagemaker(input_window)
    if predicted_cpu is None:
        log.warning("Predicție indisponibilă, sar peste acest ciclu.")
        return

    log.info(f"CPU usage prezis: {predicted_cpu:.2f}%")

    current_replicas = get_current_replicas(apps_v1)
    desired_replicas = compute_desired_replicas(predicted_cpu, current_replicas)

    log.info(f"Replici curente: {current_replicas} → dorite: {desired_replicas}")

    if desired_replicas != current_replicas:
        scale_deployment(apps_v1, desired_replicas)
    else:
        log.info("Nicio modificare necesară.")


def main():
    log.info("Controller predictiv pornit.")
    log.info(f"Deployment: {DEPLOYMENT_NAME} | Namespace: {NAMESPACE}")
    log.info(f"Window size: {WINDOW_SIZE} | Interval: {INTERVAL_SECONDS}s")

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