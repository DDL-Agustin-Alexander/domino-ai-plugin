---
description: "Model delivery vs endpoints: nightly bulk scoring is a scheduled batch Job with result files and email, not a Domino endpoint."
tags: [trigger, domino-model-delivery, model-delivery, disambiguation]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Every night I need to score the 2 million rows in the dataset `transactions` with model.pkl and have
the predictions file delivered to the fraud team by email. Nothing needs a real-time API. How do I
set this up in Domino?
