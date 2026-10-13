---
description: "Model monitoring: prediction capture via DataCaptureClient edited into predict.py, plus a registered training set as baseline."
tags: [trigger, domino-model-monitoring, monitoring]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

Edit predict.py in place so Domino Model Monitoring captures every prediction from this endpoint for
drift analysis, and tell me how to give Domino the training data it compares against.
