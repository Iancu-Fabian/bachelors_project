import requests
import boto3
import pandas as pd
import datetime
from requests_aws4auth import AWS4Auth
import os

REGION = "us-east-1"
AMP_ENDPOINT = "https://aps-workspaces.us-east-1.amazonaws.com/workspaces/ws-40558f89-8512-4916-a67f-117fb51ca37d"
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
    "request_rate": f'sum(rate(http_requests_total{{namespace="{NAMESPACE}"}}[1m])) OR on() vector(0)',
    "cpu_usage": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*"}}[1m]))',
    "memory_usage": f'sum(container_memory_working_set_bytes{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*"}})',
    "cpu_throttling_ratio": f'(sum(rate(container_cpu_cfs_throttled_seconds_total{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*"}}[1m])) / sum(rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*"}}[1m]))) OR on() vector(0)',
    "network_receive_rate": f'sum(rate(container_network_receive_bytes_total{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*"}}[1m])) OR on() vector(0)',
    "latency_p95": f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*"}}[1m])) by (le)) OR on() vector(0)',
    "error_rate": f'sum(rate(http_requests_total{{namespace="{NAMESPACE}", pod=~"{DEPLOYMENT_NAME}.*", status=~"5.."}}[1m])) OR on() vector(0)',
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
start_time = end_time - datetime.timedelta(minutes=30)

start = start_time.timestamp()
end = end_time.timestamp()

dfs = []

for name, query in QUERIES.items():
    print(f"Collecting {name}...")
    data = query_range(query, start, end)

    if data and data.get("data") and data["data"]["result"]:
        results = data["data"]["result"][0]["values"]
        temp_df = pd.DataFrame(results, columns=["timestamp", name])
        temp_df["timestamp"] = temp_df["timestamp"].astype(float)
        temp_df[name] = temp_df[name].astype(float)
        dfs.append(temp_df.set_index("timestamp"))
    else:
        print(f"Warning: No data found for {name}. Filling with 0.")

if dfs:
    final_df = pd.concat(dfs, axis=1).sort_index().interpolate().fillna(0)
    final_df.to_csv("dataset/training_dataset.csv", mode='a', header=not os.path.exists("dataset/training_dataset.csv"))
    print(f"Dataset saved with {len(final_df)} rows.")
else:
    print("No data collected at all. Check your AMP permissions or pod labels.")