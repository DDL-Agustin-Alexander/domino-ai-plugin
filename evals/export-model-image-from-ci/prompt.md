---
description: "Model delivery: build a model image and export it to a registry from CI via the Model Export API (/v4/models, internal), with a bearer token."
tags: [trigger, domino-model-delivery, model-delivery]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

From a GitHub Actions job, build the Domino model `fraud-clf` in project id 64f0c0ffee11223344556677
into a container image, push it to our registry registry.example.com/ml/fraud-clf, and tell me what
to watch while it builds. We will run the image on our own Kubernetes, not as a Domino endpoint. Put
the code in your reply, not in files.
