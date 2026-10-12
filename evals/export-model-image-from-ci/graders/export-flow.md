---
type: llm
---

PASS if the pipeline calls `POST /v4/models/buildModelImage`, polls `GET /v4/models/{modelId}/{modelVersionId}/getBuildStatus` until the build is Complete (or Failed), then calls `POST /v4/models/{modelId}/{modelVersionId}/exportImageToRegistry` with the registry details and polls `GET /v4/models/{exportId}/getExportImageStatus` (optionally fetching `getExportLogs`), authenticating with a Personal Access Token or service-account token from a GitHub secret as `Authorization: Bearer`, and reading registry credentials from secrets rather than the workflow source.
FAIL if it uses the legacy `X-Domino-Api-Key` header, deploys a Domino endpoint (`/api/modelServing/...`) instead of exporting an image, or exports before the build has completed.
