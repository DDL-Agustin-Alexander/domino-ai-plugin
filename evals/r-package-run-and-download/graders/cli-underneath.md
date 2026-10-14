---
type: llm
---

PASS if the reply uses the Domino R package (`library(domino)`, `domino.get`, `domino.run("fit.R", 0.05, 200)`, `domino.download()`) and says the package drives the installed Domino CLI, so the CLI must be installed and signed in first (`domino login`, or the device-code flow).
FAIL if it invents R functions outside the package (for example `domino.jobs_start`, `domino_api(...)`) or tells the user to pass an API key.
