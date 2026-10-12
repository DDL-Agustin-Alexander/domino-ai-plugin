---
description: "Distributed computing: connect with the RAY_HEAD_SERVICE_* and DASK_SCHEDULER_SERVICE_* variables Domino injects; no ray.init(address=auto), no SDK cluster_config."
tags: [trigger, domino-distributed-computing, clusters]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

I launched a Domino workspace with an on-demand Ray cluster attached. Show me how to connect to it
from Python and run a trivial parallel task. Then show the equivalent connection for a Dask cluster.
Put the code in your reply, not in files.
