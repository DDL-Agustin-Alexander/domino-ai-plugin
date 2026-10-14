---
type: llm
---

The user is on Domino Cloud, where the legacy AI Gateway has been removed.
PASS if the reply does BOTH of these:
1. Tells the user to store the provider API key as a Domino environment variable (Project or User settings) and read it in code (for example `os.environ["OPENAI_API_KEY"]`), or to use a Domino-hosted model endpoint; and
2. Does not present the legacy AI Gateway (the "Gateway LLMs" UI, `/api/aigateway/v1` routes, or the MLflow Deployments client) as a working option on Domino Cloud. Mentioning LLM Gateway 2.0 as a separately deployed app available through Domino is fine.
FAIL if it tells the user to create an AI Gateway endpoint, or if it hard-codes the key in the code or in git.
