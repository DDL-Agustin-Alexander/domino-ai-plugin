---
description: "Kubeflow Pipelines: a KFP component starts a Domino Job over REST with a bearer token from a secret and polls it."
tags: [trigger, domino-airflow-kubeflow, orchestration]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a Kubeflow Pipelines v2 component that starts the Domino Job `python score.py` in project id
64f0c0ffee11223344556677, waits for it, and returns the Job id. The pipeline runs on our own
cluster, not in Domino. How should the component get its Domino credential? Put the code in your
reply, not in files.
