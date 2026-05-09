import requests
import boto3
import pandas as pd
import datetime
from requests_aws4auth import AWS4Auth
import os

MODE = os.getenv("MODE", "training")
SESSION_ID = os.getenv("SESSION_ID", "0")

if MODE == "training":
    CSV_PATH = "dataset/training_dataset.csv"
elif MODE == "hpa_eval":
    CSV_PATH = "dataset/evaluation_hpa.csv"
elif MODE == "lstm_eval":
    CSV_PATH = "dataset/evaluation_lstm.csv"
else:
    CSV_PATH = f"dataset/dataset_{MODE}.csv"

def get_amp_endpoint(region: str, alias: str = "licenta-amp") -> str:
    client = boto3.client("amp", region_name=region)
    workspaces = client.list_workspaces(alias=alias)["workspaces"]
    if not workspaces:
        raise RuntimeError(f"No AMP workspace found with alias '{alias}'")
    workspace = workspaces[0]
    return f"https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace['workspaceId']}"

REGION = "us-east-1"
AMP_ENDPOINT = get_amp_endpoint(REGION)
NAMESPACE = "default"
DEPLOYMENT_NAME = "api-deployment"

session = boto3.Session()
credentials = session.get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "aps",
    session_token=credentials.token
)

QUERIES = {
    "request_rate": f'sum(rate(http_requests_total{{handler="/predict"}}[1m])) OR on() vector(0)',
    "cpu_usage": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*", container="api"}}[1m]))',
    "latency_p95": f'histogram_quantile(0.95, sum(rate(http_request_duration_highr_seconds_bucket[1m])) by (le)) * on() (sum(rate(http_requests_total{{handler="/predict"}}[1m])) > bool 0) OR on() vector(0)',
    "error_rate": f'(sum(rate(http_requests_total{{handler="/predict", status=~"5.."}}[1m])) / sum(rate(http_requests_total{{handler="/predict"}}[1m]))) OR on() vector(0)',
    "replica_count": f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}", deployment="{DEPLOYMENT_NAME}"}} OR on() vector(0)'
}

def query_range(query, start, end, step="30s"):
    try:
        response = requests.get(
            f"{AMP_ENDPOINT}/api/v1/query_range",
            auth=awsauth,
            params={"query": query, "start": start, "end": end, "step": step},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        return None

end_time = datetime.datetime.now(datetime.UTC)
start_time = end_time - datetime.timedelta(minutes=5)
start = start_time.timestamp()
end = end_time.timestamp()

dfs = []

for name, query in QUERIES.items():
    data = query_range(query, start, end)

    if data and data.get("data") and data["data"]["result"]:
        results = data["data"]["result"][0]["values"]
        temp_df = pd.DataFrame(results, columns=["timestamp", name])
        temp_df["timestamp"] = temp_df["timestamp"].astype(float)
        temp_df[name] = temp_df[name].astype(float)
        dfs.append(temp_df.set_index("timestamp"))

if dfs:
    final_df = pd.concat(dfs, axis=1).sort_index().interpolate().fillna(0)

    if "replica_count" in final_df.columns:
        final_df["replica_count"] = final_df["replica_count"].replace(0, pd.NA).ffill().fillna(0)

    final_df["session_id"] = SESSION_ID

    os.makedirs("dataset", exist_ok=True)

    if os.path.exists(CSV_PATH) and os.path.getsize(CSV_PATH) > 0:
        existing_df = pd.read_csv(CSV_PATH, index_col=0)
        final_df = pd.concat([existing_df, final_df])
        final_df = final_df[~final_df.index.duplicated(keep='last')]

    final_df.to_csv(CSV_PATH)
    print(f"Dataset saved with {len(final_df)} total rows to {CSV_PATH}. Session: {SESSION_ID}")
else:
    print("No data collected at all.")