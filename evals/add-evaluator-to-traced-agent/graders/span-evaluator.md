---
type: llm
focus: { source: file, path: agent.py }
---

PASS if the evaluator passed to `@add_tracing(evaluator=...)` is a function that takes the completed span as its single argument and reads `span.inputs` / `span.outputs` (or equivalent attributes of that span object), returning a dict of metric name to number or string.
FAIL if the evaluator is written with an `(inputs, output)` or `(question, answer)` signature as what the SDK calls.
