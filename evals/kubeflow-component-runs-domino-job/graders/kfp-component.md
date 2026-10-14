---
type: llm
---

PASS if the component (a `@dsl.component` using `requests`) posts to `/api/jobs/v1/jobs` with `projectId` and `runCommand`, polls `GET /api/jobs/beta/jobs/{jobId}` until `status.isCompleted` or a terminal `executionStatus`, and reads a Personal Access Token or Domino service-account token from a Kubernetes Secret injected as an environment variable, sent as `Authorization: Bearer` to the deployment URL.
FAIL if it uses a legacy API key, hard-codes the token in the pipeline source, or relies on `DOMINO_API_PROXY` or `localhost:8899` inside the component.
