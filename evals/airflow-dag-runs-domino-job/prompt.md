---
description: "Airflow: a task starts a Domino Job through the Jobs API, polls to a terminal state, fails on non-success; worker auth is a PAT or service-account bearer."
tags: [trigger, domino-airflow-kubeflow, orchestration]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

We run Apache Airflow 2.x outside Domino. Write a DAG task that starts the Domino Job `python
train.py` in project id 64f0c0ffee11223344556677 and fails the task unless the Job succeeds, and
tell me how the worker authenticates to Domino. Put the code in your reply, not in files.
