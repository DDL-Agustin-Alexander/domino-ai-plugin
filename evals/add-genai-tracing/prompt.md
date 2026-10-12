---
description: Tracing setup adds the Domino SDK decorator and run context to an OpenAI agent.
tags: [trigger, converted-command, genai, domino-trace-setup, domino-genai-tracing]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

I run this little OpenAI agent in Domino. Instrument agent.py in place so I can see each LLM call and its latency in Domino, grouped as one run.
