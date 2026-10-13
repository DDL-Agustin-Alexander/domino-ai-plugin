---
description: "Flows: DominoJobTask + DominoJobConfig under @workflow in flow.py, launched with pyflyte run --remote."
tags: [trigger, domino-flows, flows]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

Create a Domino Flow in flow.py that runs stages/prep.py and then stages/train.py as two tasks,
passing the path prep produces into train, and tell me how to launch it.
