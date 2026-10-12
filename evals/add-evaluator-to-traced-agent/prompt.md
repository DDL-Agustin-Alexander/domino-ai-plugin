---
description: "GenAI tracing: evaluators receive the span; DominoRun has no run_name; results grouped in one run."
tags: [trigger, domino-genai-tracing, genai]
max_turns: 15
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

agent.py is already traced with @add_tracing. Add an evaluator in agent.py through the Domino SDK's evaluator hook
on that decorator, scoring each answer for relevance (an LLM-as-judge is fine) so the score appears on the
trace in Domino, and write run_eval.py that runs three sample questions as one experiment run.
