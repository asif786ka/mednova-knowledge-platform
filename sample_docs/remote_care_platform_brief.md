# Project Brief — Remote Care Platform

**Client:** Northgate Clinics Group
**Project:** Remote Care Platform

## Summary
The Remote Care Platform supports remote patient monitoring for chronic-care patients. It ingests
device telemetry and alerts clinicians. It uses AI automation to detect anomalies in vital signs.

## Technologies
The Remote Care Platform uses **FastAPI** for its API, **PostgreSQL** for records, and **Kafka**
for streaming device telemetry. It is a cloud-based healthcare system.

## Cloud deployment
The Remote Care Platform is deployed on **Google Cloud Platform (GCP)** using GKE. Cloud
deployment uses autoscaling node pools for telemetry spikes.

## Requirements
- Real-time alerting with sub-second processing of telemetry.
- Related to patient engagement through automated check-in reminders.
