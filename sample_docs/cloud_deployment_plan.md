# Cloud Deployment Plan

This plan covers cloud deployment for MedNova projects and the cloud providers used.

## Cloud providers
- The MedNova Knowledge Platform is deployed on **AWS** (ECS, ElastiCache Redis).
- The Patient Assistant Platform is deployed on **Microsoft Azure** (AKS).
- The Remote Care Platform is deployed on **Google Cloud Platform (GCP)** (GKE).
- The Operational Insights Service is deployed on **AWS** (Lambda + Fargate).

## Notes
Each deployment uses container orchestration and autoscaling. Cloud deployment boundaries isolate
patient data per client. Documents mentioning cloud deployment include this plan, the Knowledge
Platform design, and both patient project briefs.
