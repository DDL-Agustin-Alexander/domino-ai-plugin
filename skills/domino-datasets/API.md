# Dataset REST API

All routes below exist in both published Public API specs
(https://docs.domino.ai/api-specs/6.3/public-api.json and
https://docs.domino.ai/api-specs/cloud/public-api.json, tag `Datasets`) and were checked against
a live Domino 6.4.0 deployment with read-only calls on 2026-10-12. No `/v4` route is needed.
Docs: https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/datasets/create-and-manage-datasets
(REST tab) and the API reference under https://docs.domino.ai/cloud/reference/api.

## Authentication

Inside a Domino execution call the proxy with no header; it adds the starting user's token.
Outside, use a Personal Access Token or service-account token as a bearer against the
deployment URL (domino-api-intro skill). Legacy user API keys are deprecated; do not use them.

```bash
# inside a Workspace, Job or App
curl -sS "$DOMINO_API_PROXY/api/datasetrw/v2/datasets?limit=50"

# outside Domino
curl -sS -H "Authorization: Bearer $DOMINO_TOKEN" "$DOMINO_API_HOST/api/datasetrw/v2/datasets?limit=50"
```

```python
import os
import requests

base = os.environ.get("DOMINO_API_PROXY") or os.environ["DOMINO_API_HOST"]
headers = {} if os.environ.get("DOMINO_API_PROXY") else {"Authorization": f"Bearer {os.environ['DOMINO_TOKEN']}"}
r = requests.get(f"{base}/api/datasetrw/v2/datasets", headers=headers, params={"limit": 50})
r.raise_for_status()
```

Every response wraps the payload with `metadata` (`requestId`, `notices`, and on lists `offset`,
`limit`, sometimes `totalCount`). Errors return `{"requestId": ..., "errors": ["..."]}`.

## Routes

| Method and path | Purpose | Body or parameters |
|---|---|---|
| `GET /api/datasetrw/v2/datasets` | Datasets the caller can access | `limit` (default 10), `offset`, `projectIdsToInclude` or `projectIdsToExclude`, `includeProjectInfo`, `includeArchivedProjects`, `minimumPermission` (for example `ReadDatasetRwV2`, `UpdateDatasetRwV2`) |
| `POST /api/datasetrw/v1/datasets` | Create | `{"name": "...", "description": "...", "projectId": "...", "grants": [...]}`; or `snapshotId` instead of `projectId` to copy a snapshot into a new Dataset; `name` required |
| `GET /api/datasetrw/v1/datasets/{datasetId}` | Details | returns `id`, `name`, `description`, `projectId`, `createdAt`, `snapshotIds`, `tags` (tag name to snapshot ID) |
| `PATCH /api/datasetrw/v1/datasets/{datasetId}` | Rename or re-describe | `{"name": "...", "description": "..."}` (either) |
| `DELETE /api/datasetrw/v1/datasets/{datasetId}` | Mark for deletion | none; an admin performs the permanent delete |
| `GET /api/datasetrw/v1/datasets/{datasetId}/snapshots` | List snapshots | `offset`, `limit` (default 10); each has `id`, `datasetId`, `creatorId`, `createdAt`, `status` |
| `POST /api/datasetrw/v1/datasets/{datasetId}/snapshots` | Create snapshot | `{"relativeFilePaths": ["/*"]}` for all files, or specific paths; returns `status: pending` |
| `GET /api/datasetrw/v1/snapshots/{snapshotId}` | Snapshot details | `status` is one of `pending`, `active`, `failed`, `copying`, `markForDeletion`, `deletionInProgress`, `deleted` |
| `POST /api/datasetrw/v1/datasets/{datasetId}/tags` | Tag a snapshot (remove first to move an existing tag) | `{"snapshotId": "...", "tagName": "..."}` |
| `DELETE /api/datasetrw/v1/datasets/{datasetId}/tags/{tagName}` | Remove a tag | none |
| `GET /api/datasetrw/v1/datasets/{datasetId}/grants` | List grants | none |
| `POST /api/datasetrw/v1/datasets/{datasetId}/grants` | Add a grant | `{"targetId": "<user-id>", "targetRole": "DatasetRwOwner" / "DatasetRwEditor" / "DatasetRwReader"}` |
| `DELETE /api/datasetrw/v1/datasets/{datasetId}/grants` | Remove a grant | same body as add |
| `GET /api/projects/v1/projects/{projectId}/shared-datasets` | Datasets shared into a Project | 404 with `sharedDatasetRwEntry ... not found` when none |
| `POST /api/projects/v1/projects/{projectId}/shared-datasets` | Mount a shared Dataset | `{"datasetId": "..."}`; needs `ManageDatasetsRw` and `UseFileStorage` on the Project |
| `DELETE /api/projects/v1/projects/{projectId}/shared-datasets/{datasetId}` | Unmount | none |
| `GET /datasetrw/snapshot/{snapshotId}/files/recursive?path=` | File names under a path in a snapshot | `path` required (`/` for the root) |
| `GET /datasetrw/snapshot/{snapshotId}/file/raw?path=` | Raw file content | `path` required; `download` optional |

`GET /api/datasetrw/v1/datasets` also exists but is marked deprecated; use v2. The `/datasetrw/...`
file routes are in the Public API spec without the `/api` prefix; chunked upload routes
(`/datasetrw/datasets/{datasetId}/snapshot/file/...`) exist but are what the CLI and
python-domino `datasets_upload_files` drive; prefer those tools over calling them directly.

## Examples

Create a Dataset in the current Project and snapshot it after writing files:

```bash
DS=$(curl -sS -X POST "$DOMINO_API_PROXY/api/datasetrw/v1/datasets" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"training-data\", \"description\": \"Q3 features\", \"projectId\": \"$DOMINO_PROJECT_ID\", \"grants\": []}")
DATASET_ID=$(printf '%s' "$DS" | python3 -c "import sys, json; print(json.load(sys.stdin)['dataset']['id'])")

# ... write files under the mount path, then:
curl -sS -X POST "$DOMINO_API_PROXY/api/datasetrw/v1/datasets/$DATASET_ID/snapshots" \
  -H "Content-Type: application/json" -d '{"relativeFilePaths": ["/*"]}'
```

The new Dataset is mounted in executions started after it exists; a running Workspace does not
see it until restarted.

Wait for a snapshot, then tag it:

```python
import time

snap = requests.post(f"{base}/api/datasetrw/v1/datasets/{dataset_id}/snapshots",
                     headers=headers, json={"relativeFilePaths": ["/*"]}).json()["snapshot"]
while snap["status"] == "pending":
    time.sleep(5)
    snap = requests.get(f"{base}/api/datasetrw/v1/snapshots/{snap['id']}", headers=headers).json()["snapshot"]
assert snap["status"] == "active", snap
requests.post(f"{base}/api/datasetrw/v1/datasets/{dataset_id}/tags", headers=headers,
              json={"snapshotId": snap["id"], "tagName": "production"}).raise_for_status()
```

Find a Dataset by name across Projects:

```python
r = requests.get(f"{base}/api/datasetrw/v2/datasets", headers=headers,
                 params={"limit": 200, "includeProjectInfo": "true"})
match = next(d["dataset"] for d in r.json()["datasets"] if d["dataset"]["name"] == "training-data")
```

Share with a user and mount in another Project:

```python
requests.post(f"{base}/api/datasetrw/v1/datasets/{dataset_id}/grants", headers=headers,
              json={"targetId": user_id, "targetRole": "DatasetRwReader"}).raise_for_status()
requests.post(f"{base}/api/projects/v1/projects/{other_project_id}/shared-datasets", headers=headers,
              json={"datasetId": dataset_id}).raise_for_status()
```

Snapshot limit hit: `POST .../snapshots` or an execution that writes a snapshot fails; list
snapshots, `DELETE` is not available per snapshot in the Public API, so mark old ones for
deletion in the UI and have an admin remove them, or raise the limit.

## python-domino

The SDK wraps a subset: `datasets_list(project_id=None)`, `datasets_ids(project_id)`,
`datasets_names(project_id)`, `datasets_create(dataset_name, dataset_description)`,
`datasets_details(dataset_id)`, `datasets_update_details(dataset_id, dataset_name=None,
dataset_description=None)`, `datasets_remove(dataset_ids)`, and `datasets_upload_files(...)`.
It has no snapshot, tag, grant or shared-dataset methods; use the routes above. See the
domino-python-sdk skill.
