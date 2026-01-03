#!/bin/bash
# ================================================
# Pause (shut down) your EKS cluster to save costs
# ================================================

# Change these if needed
CLUSTER_NAME="basic-cluster"
REGION="us-east-1"

echo "Checking cluster status..."
if ! eksctl get cluster --region $REGION | grep -q $CLUSTER_NAME; then
  echo "Cluster $CLUSTER_NAME not found in region $REGION"
  exit 1
fi

echo "Listing nodegroups..."
NODEGROUPS=$(eksctl get nodegroup --cluster $CLUSTER_NAME --region $REGION -o json | jq -r '.[].Name')

if [ -z "$NODEGROUPS" ]; then
  echo "No nodegroups found (already paused)."
else
  echo "Deleting nodegroups..."
  for NG in $NODEGROUPS; do
    echo "Deleting nodegroup $NG..."
    eksctl delete nodegroup --cluster $CLUSTER_NAME --region $REGION --name $NG --disable-eviction
  done
fi

read -p "Do you also want to delete the entire cluster (y/N)? " DELETE_CLUSTER
if [[ "$DELETE_CLUSTER" =~ ^[Yy]$ ]]; then
  echo "Deleting cluster $CLUSTER_NAME..."
  eksctl delete cluster --name $CLUSTER_NAME --region $REGION --wait
  echo "Cluster deleted completely."
else
  echo "Cluster control plane kept (you'll still pay ~$0.10/hour)."
fi

echo "Done. All compute resources stopped."
