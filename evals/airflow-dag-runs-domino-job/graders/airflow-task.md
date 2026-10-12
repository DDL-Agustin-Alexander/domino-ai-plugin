---
type: llm
---

PASS if the task starts the Job with `POST /api/jobs/v1/jobs` (body with `projectId` and `runCommand`) or python-domino's `job_start` / `DominoOperator`, waits by polling the Job status (`GET /api/jobs/beta/jobs/{jobId}` reading `status.executionStatus`, or a blocking SDK call), raises or fails the task when the Job ends in any state other than Succeeded (Failed, Stopped, Error), and authenticates with a Personal Access Token or Domino service-account token kept in Airflow's secret store or a token file, sent as `Authorization: Bearer` to the deployment URL.
FAIL if it tells the user to store a legacy Domino API key (`DOMINO_API_KEY` / `X-Domino-Api-Key`) as the credential, uses `DOMINO_API_PROXY` or `localhost:8899` on the Airflow worker, or treats a Failed or Stopped Job as success.
