---
type: llm
---

PASS if the reply recommends the provider SDK with the API key stored as a Domino environment variable (read via os.environ) as the default path, and, if it mentions the AI Gateway at all, says it is legacy and not enabled by default on 6.3 (usable only where an administrator enabled it). Mentioning LLM Gateway 2.0 as a separately distributed app is fine.
FAIL if it presents the AI Gateway ("Gateway LLMs", /api/aigateway routes, MLflow deployments client) as the default or always-available path on 6.3, or if it tells the user to hard-code the key.
