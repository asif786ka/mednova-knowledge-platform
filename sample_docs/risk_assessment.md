# Risk Assessment — MedNova Projects

This document lists risks mentioned across MedNova project documents.

## Data privacy and compliance risk
All patient-facing projects (Patient Assistant Platform, Remote Care Platform) carry a **HIPAA /
data-privacy risk**. Patient data must be encrypted in transit and at rest.

## Model hallucination risk
The MedNova Knowledge Platform has a **hallucination risk**: the LLM may invent unsupported
answers. Mitigation: source-backed answers and an explicit "not enough information" fallback.

## Latency risk
The Patient Assistant Platform and Remote Care Platform have a **latency risk** for real-time
voice and telemetry. Mitigation: caching and streaming.

## Vendor lock-in risk
Using managed services such as Astra DB and Neo4j introduces a **vendor lock-in risk**.
Mitigation: the LiteLLM provider abstraction and interface-bound stores.

## Speech recognition accuracy risk
The Patient Assistant Platform has a **speech-recognition-accuracy risk** for accented or
multilingual speech.
