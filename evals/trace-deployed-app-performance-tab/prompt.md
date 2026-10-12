---
description: "GenAI tracing in production: @add_tracing alone is enough for a deployed app; DominoRun/DominoAgentContext is optional there."
tags: [trigger, domino-genai-tracing, genai]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

This FastAPI chat service will be deployed as a Domino App. Edit main.py in place so its LLM calls
are traced and show up in Domino for the deployed app, and tell me whether I need a DominoRun /
DominoAgentContext around each request.
