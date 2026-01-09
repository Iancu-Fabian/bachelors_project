#!/bin/bash

CONFIG_FILE="clusterconfig.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "clusterconfig.yaml not found in current directory."
  exit 1
fi

echo "Recreating cluster from $CONFIG_FILE..."
eksctl create cluster -f $CONFIG_FILE

echo "Applying manifests..."
if [ -d "manifests" ]; then
  kubectl apply -f manifests/
  echo "App redeployed."
else
  echo "No ./manifests directory found — skipping app deployment."
fi

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring || true

helm upgrade --install prometheus \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --wait

echo "Cluster restored and ready to use!"
