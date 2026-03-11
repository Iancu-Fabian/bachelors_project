import boto3
import requests
from requests_aws4auth import AWS4Auth
import datetime

def get_amp_endpoint(region: str, alias: str = "licenta-amp") -> str:
    client = boto3.client("amp", region_name=region)
    workspaces = client.list_workspaces(alias=alias)["workspaces"]
    workspace = workspaces[0]
    return f"https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace['workspaceId']}"

REGION = "us-east-1"
AMP_ENDPOINT = get_amp_endpoint(REGION)

session = boto3.Session()
credentials = session.get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "aps",
    session_token=credentials.token
)

def instant_query(query):
    response = requests.get(
        f"{AMP_ENDPOINT}/api/v1/query",
        auth=awsauth,
        params={"query": query, "time": datetime.datetime.now(datetime.UTC).timestamp()},
        timeout=10
    )
    data = response.json()
    result = data.get("data", {}).get("result", [])
    print(f"Query: {query}")
    print(f"Result: {result if result else 'NO DATA'}")
    print()

# 1. check if the metric exists at all in AMP
instant_query('http_requests_total')

# 2. check with just the handler label
instant_query('http_requests_total{handler="/predict"}')

# 3. check what labels actually exist on the metric
instant_query('http_requests_total{handler=~".+"}')

# 4. check if ServiceMonitor is scraping at all
instant_query('up{job=~".*api.*"}')

# 5. check rate
instant_query('rate(http_requests_total{handler="/predict"}[1m])')