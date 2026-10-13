---
type: llm
---

PASS if the reply says that in a deployed app `DominoRun` / `DominoAgentContext` is not required around each request: the `@add_tracing` decorator (with framework autologging) alone captures production traces, which Domino shows for the deployed app.
FAIL if it says every request must be wrapped in `DominoRun` or `DominoAgentContext` for traces to appear for the deployed app.
