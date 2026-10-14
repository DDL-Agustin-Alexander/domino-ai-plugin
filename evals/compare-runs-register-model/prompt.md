---
description: "Experiment tracking: compare runs with MLflow search, register the best run's model with MLflow registry APIs."
tags: [trigger, domino-experiment-tracking, experiments, disambiguation]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

I have logged twenty runs to my Domino experiment `churn-alice`. From code, find the run with the
highest `val_auc`, and register that run's logged model in the Domino model registry as `churn-clf`.
Put the code in your reply, not in files.
