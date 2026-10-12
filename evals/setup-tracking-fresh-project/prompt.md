---
description: "Disambiguation: a from-scratch experiment-tracking setup loads domino-experiment-setup and writes a deployment-unique experiment name."
tags: [trigger, domino-experiment-setup, experiments, disambiguation]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

This project has no experiment tracking yet. Set it up so every training run lands in Domino's
Experiment Manager under a name that will not collide with other users' experiments, with
autologging on. Put the helper code in experiment_setup.py and wire it into train.py.
