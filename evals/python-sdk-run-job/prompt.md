---
description: "python-domino: Domino(project) without api_key, job_start / job_start_blocking, job_status; no invented methods."
tags: [trigger, domino-python-sdk, api, disambiguation]
max_turns: 12
allowed_tools: [Read, Glob, Grep, Skill]
---

Using the python-domino library from inside my Domino workspace, start a job that runs train.py in
my project `alice/churn`, wait for it to finish, and print its final status. Put the code in your
reply, not in files.
