# CSV Processor Platform

A cloud-native, highly available, and auto-scaling data platform built on AWS using Kubernetes (`kops`), Docker, Helm, and Ansible. This platform features a high-performance Python Flask engine with an Nginx sidecar architecture that securely parses, displays, and archives corporate CSV datasets to Amazon S3 with an automated Glacier transition lifecycle policy.

---

## Architecture Overview

The platform uses a sidecar pattern to optimize static file performance and secure dynamic request processing without relying on complex, external Network File Systems (NFS):

1. **Front-Facing Nginx Sidecar**: Intercepts external web traffic. If a static asset (`/assets/`) is requested, Nginx serves it directly out of a high-speed, localized shared `emptyDir` volume. All other traffic is reverse-proxied to the backend over a localhost loopback interface.
2. **Python Flask Processing Engine**: Handles CSV uploads, reads files line-by-line to stream them to the browser, and securely writes datasets directly to Amazon S3.
3. **Cluster Autoscaler & Spot Optimization**: Instantiates worker pools across 3 Availability Zones using a split strategy (100% On-Demand and 100% Spot instances) to optimize infrastructure costs, supported by the AWS Node Termination Handler.
4. **S3 Storage Lifecycle**: Datasets uploaded to S3 reside in standard storage for 30 days before being automatically transitioned to cost-effective S3 Glacier flexible storage.

---

## Directory Hierarchy

```text
📁 csv-processor-platform/              # Root Project Directory
│
├── 📁 app/                             # 1. APPLICATION SOURCE CODE
│   ├── app.py                          # Flask application entry point & logic
│   ├── Dockerfile                      # Multistage container build definition
│   └── requirements.txt                # Python dependencies (Flask, boto3, etc.)
│
├── 📁 deploy/                          # 2. INFRASTRUCTURE & ORCHESTRATION
│   │
│   ├── 📁 ansible/                     # Ansible (Configuration Management)
│   │   ├── inventory.ini               # Host / Target cluster definitions
│   │   ├── site-deploy.yml             # Main playbook executing environment tasks
│   │   └── 📁 group_vars/              # Environment-specific CM Variables
│   │       ├── all.yml                 # Global shared values
│   │       ├── staging.yml             # Staging specific overrides
│   │       └── production.yml          # Production specific overrides
│   │
│   └── 📁 helm/                        # Reusable Helm Chart
│       └── 📁 csv-processor/           # Chart definition folder
│           ├── Chart.yaml              # Chart metadata
│           ├── values.yaml             # Baseline chart default values
│           └── 📁 templates/           # Kubernetes manifests using Go-templating
│               ├── _helpers.tpl        # Reusable label and naming macros
│               ├── configmap-nginx.yaml# Nginx configuration (reverse-proxy)
│               ├── deployment.yaml     # Multi-container Pod (Flask + Nginx)
│               ├── hpa.yaml            # Horizontal Pod Autoscaler configuration
│               ├── service.yaml        # Service network mapper
│               └── serviceaccount.yaml # Associates AWS IAM Roles (IRSA)


============================================================================================================================
Step-by-Step Deployment Guide

Phase 1: Provisioning the Kubernetes Infrastructure (kops)

Before deploying the application layer, ensure your underlying cluster is created across 3 Availability Zones using kops with the Cluster Autoscaler and Node Termination Handler enabled.

1. Ensure S3 State Store and environment variables are initialized:

export KOPS_CLUSTER_NAME=ss-cluster.example.com
export KOPS_STATE_STORE=s3://ss-kops-state-store-bucket

2. Generate cluster manifest using cluster configuration file, making sure cluster configuration contains the Cluster Autoscaler addon:

```
clusterAutoscaler:
  enabled: true
  expander: least-waste
  balanceSimilarNodeGroups: true
nodeTerminationHandler:
  enabled: true
  enableSQSTerminationDraining: true
```

3. Build and apply multi-AZ infrastructure (Master nodes and split Worker instance groups for Spot and On-Demand):

kops update cluster --name ${KOPS_CLUSTER_NAME} --yes --admin
kops validate cluster --wait 10m



Phase 2: Configuring the AWS S3 Bucket Lifecycle Policy

To transition processed files to Glacier automatically, apply the lifecycle rule to designated target S3 buckets via the AWS CLI or Terraform.

Using AWS Lifecycle JSON Configuration by adding these lines to lifecycle.json file:
```
{
  "Rules": [
    {
      "ID": "MoveToGlacierAfter30Days",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```
Apply via AWS CLI:

aws s3api put-bucket-lifecycle-configuration \
  --bucket company-staging-csv-data-vault \
  --lifecycle-configuration lifecycle.json



Phase 3: Building and Pushing the Application Image

Navigate to the application folder to compile the container image using the multi-stage Dockerfile.

1.  Build the production-ready image:

docker build -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/csv-processor-app:v1.0.0 ./app

docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/csv-processor-app:v1.0.0


Phase 4: Deploying Environments with Ansible Configuration Management

Ansible acts as the orchestrator, decoupling configuration variables (min/max replicas, bucket names, and regions) from reusable Helm chart templates.

1. Install the required Ansible and Kubernetes collections on your deployment machine:
ansible-galaxy collection install kubernetes.core

2. Move into the Ansible deployment directory:
cd deployment/ansible

3. Deploy to your targeted environment (Staging or Production). Ansible will automatically read environmental overrides from group_vars/, verify the namespace exists, render the Helm variables, and safely trigger the rolling update:

- Deploying to Staging:

$ ansible-playbook -i inventory.ini site-deploy.yml -e "target_env=staging"

- Deploying to Production:

$ ansible-playbook -i inventory.ini site-deploy.yml -e "target_env=production"



==========================================================================================

Verifying Deployment Components

Once deployed, verify that all components are functioning as expected within your target environment namespace:


# Check the status of your Multi-Container Pods
kubectl get pods -n app-csv-staging

# Check that the Horizontal Pod Autoscaler is tracking live CPU values
kubectl get hpa -n app-csv-staging

# View logs from the Flask CSV parser processing engine container
kubectl logs deployment/staging-csv-processor -c processing-engine -n app-csv-staging

# View logs from the front-facing Nginx container
kubectl logs deployment/staging-csv-processor -c nginx-proxy -n app-csv-staging
