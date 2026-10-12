# Errors and retries (agents)

How to interpret Domino API failures, when to retry, and when to change approach.
Pagination lives in [LIMITS.md](./LIMITS.md). Auth mistakes look like 401/403; fix the
mode per [SKILL.md](./SKILL.md#authentication) before retrying.

## Error bodies

The Public API spec declares two error shapes:

```json
{"errors": ["human-readable message", "..."], "requestId": "..."}
```

for Nucleus `/api/...` routes (schema `Error`), and

```json
{"message": "human-readable message"}
```

for the taxonomy (`/api/taxonomy/v1`) and NetApp (`/remotefs/v1`) services. Some V1
schemas return `{"code": "...", "message": "..."}` (`ErrorV1`). Read the message before
retrying. An HTML or empty body on a 5xx is an infrastructure failure, not a validation
problem.

## HTTP status: retry or not

| Code | Agent action |
|------|----------------|
| **400** | Fix the body, path or query against the spec. Do not retry blindly. |
| **401** | Missing or expired token, or wrong auth mode for where the code runs. Fix auth per [SKILL.md](./SKILL.md#authentication). |
| **403** | Permission. Retrying will not help; change the role, project or resource, or ask an admin. |
| **404** | Wrong id, wrong base URL, or the route is not served where you called it. Check the id, then the base URL per [HOSTS.md](./HOSTS.md). |
| **409** | Conflict (duplicate name, state). Fetch the current state and reconcile. |
| **502 / 504 / timeout** | Response too large or upstream overloaded. Reduce page size, paginate, then retry with backoff only if the call is idempotent. |
| **500** | Retry once with backoff if idempotent; otherwise stop and surface the error with its `requestId`. |

## Jobs and execution status

`GET /api/jobs/beta/jobs/{jobId}` returns `{"job": {...}, "metadata": {...}}`. Status is the
object `job.status` with `executionStatus` (string), `isCompleted`, `isArchived` and
`isScheduled`. Treat `isCompleted: true` as terminal and read `executionStatus` for the
outcome. Values seen on live deployments and tested by python-domino: `Succeeded`,
`Failed`, `Stopped`, plus `Running` and queued states while in flight.

`GET /api/jobs/beta/jobs?projectId=...` filters with `statusFilter` =
`all | queued | running | completed | archived | active`.

A missing or stale status while a job is still active is not a failure: keep polling with
backoff. See [API-JOBS.md](../domino-python-sdk/API-JOBS.md) and [domino-jobs](../domino-jobs/SKILL.md).

## Large audit and export reads

Prefer the paginated routes over one-shot dumps:

- Platform audit: `GET /api/audittrail/v1/auditevents` with `limit`/`offset` and
  `startTimestamp`/`endTimestamp` (epoch milliseconds), or `POST /api/audittrail/v1/search`
  (`limit` <= 1000). Details: [API-ADMIN.md](../domino-python-sdk/API-ADMIN.md#audit-events-api).
- Data source audit: `GET /api/datasource/v1/audit` with `startTime`/`endTime`
  (ISO 8601), `dataSourceNames` and `eventKinds` filters. Documented at
  https://docs.domino.ai/cloud/admin/operations/audit-logs/monitor-data-source-logs.
- Governance exports: paginate `GET /api/governance/v1/results?bundleID=...` with
  `offset`/`limit` (see [domino-governance](../domino-governance/SKILL.md)).

## Wrong-surface symptoms

These look like 404 or connection errors rather than a JSON error body:

- Predictions sent to `$DOMINO_API_HOST/api/modelServing/...`: invoke the `url` shown on
  the Model API's page instead, with the endpoint's own access token (sync endpoints use
  HTTP Basic with the token as both username and password; async endpoints use
  `Authorization: Bearer`). See [HOSTS.md](./HOSTS.md#model-api-invocation).
- Governance 404 on the in-run base: the governance skill falls back to the deployment
  URL with a PAT or service account token. See [HOSTS.md](./HOSTS.md#governance).

## Safe 4xx handling

- Never escalate a 401/403 into a legacy API key.
- Do not re-POST a create on 400 hoping the server accepts a second shape; read the
  error and fix the fields against the spec.
- After a failed start (job, app, model API), GET the resource before issuing the same
  POST again.
