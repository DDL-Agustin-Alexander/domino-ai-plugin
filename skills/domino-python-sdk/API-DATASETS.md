# Domino Datasets API

Create and manage Datasets, snapshots, tags and grants with the Public API. Routes and
bodies are from both published specs. Product docs:
https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/datasets and the
[domino-datasets](../domino-datasets/SKILL.md) skill.

## Authentication

Use the shared setup block (`base_url`, `headers`) from
[domino-api-intro](../domino-api-intro/SKILL.md#authentication).

## List datasets

```
GET /api/datasetrw/v2/datasets
```

| Parameter | Notes |
|-----------|-------|
| `projectIdsToInclude`, `projectIdsToExclude` | Repeatable project id filters |
| `minimumPermission` | For example `ListDatasetRwV2`, `DeleteDatasetRwV2` |
| `includeProjectInfo`, `includeArchivedProjects` | boolean |
| `offset`, `limit` | Pagination |

Response: `{"datasets": [{"dataset": {"id", "name", "description", "projectId", "createdAt", "snapshotIds", "tags"}}], "metadata": {...}}`.
Note the nested `dataset` key. `GET /api/datasetrw/v1/datasets?projectId=...` is the
simpler v1 list.

```python
datasets = requests.get(f"{base_url}/api/datasetrw/v2/datasets", headers=headers,
                        params={"projectIdsToInclude": [project_id], "limit": 50}).json()
for item in datasets["datasets"]:
    ds = item["dataset"]
    print(ds["name"], ds["id"], len(ds["snapshotIds"]))
```

## Create a dataset

```
POST /api/datasetrw/v1/datasets
```

Body: `name` (required), `projectId`, optional `grants`
(`[{"targetId": "<user-or-org-id>", "targetRole": "DatasetRwOwner|DatasetRwEditor|DatasetRwReader"}]`)
and `snapshotId`. There is no `description` field on create; set it afterwards with the UI
or python-domino `datasets_update_details`.

```python
dataset = requests.post(f"{base_url}/api/datasetrw/v1/datasets", headers=headers, json={
    "name": "customer-features",
    "projectId": project_id,
}).json()
```

## Get, update, delete

```
GET    /api/datasetrw/v1/datasets/{datasetId}
PATCH  /api/datasetrw/v1/datasets/{datasetId}     body: {"name": "new-name"}
DELETE /api/datasetrw/v1/datasets/{datasetId}
```

`PATCH` accepts only `name`.

## Snapshots

```
GET  /api/datasetrw/v1/datasets/{datasetId}/snapshots
POST /api/datasetrw/v1/datasets/{datasetId}/snapshots     body: {"relativeFilePaths": ["data/train.parquet", ...]}
GET  /api/datasetrw/v1/snapshots/{snapshotId}
```

`relativeFilePaths` is required: the paths, relative to the dataset root, to include in
the snapshot (documented at
https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/datasets/version-data-with-snapshots).
Tags are added separately (below); there is no `tag` field on snapshot create.

```python
snapshot = requests.post(f"{base_url}/api/datasetrw/v1/datasets/{dataset_id}/snapshots",
                         headers=headers, json={"relativeFilePaths": ["features.parquet"]}).json()
```

## Tags

```
POST   /api/datasetrw/v1/datasets/{datasetId}/tags            body: {"snapshotId": "<snapshot-id>", "tagName": "v1.0"}
DELETE /api/datasetrw/v1/datasets/{datasetId}/tags/{tagName}
```

Both body fields are required.

## Grants (permissions)

```
GET    /api/datasetrw/v1/datasets/{datasetId}/grants
POST   /api/datasetrw/v1/datasets/{datasetId}/grants     body: {"targetId": "<user-or-org-id>", "targetRole": "DatasetRwReader"}
DELETE /api/datasetrw/v1/datasets/{datasetId}/grants     body: {"targetId": "<user-or-org-id>", "targetRole": "DatasetRwReader"}
```

`targetRole` is `DatasetRwOwner`, `DatasetRwEditor` or `DatasetRwReader`; organizations
cannot be owners. `DELETE` takes the same body.

## Mount paths inside executions

From https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/datasets/use-datasets-and-snapshots:

| Project type | Live dataset (read-write) | Snapshot by tag / by number (read-only) |
|--------------|---------------------------|------------------------------------------|
| DFS | `/domino/datasets/local/<name>` | `/domino/datasets/local/snapshots/<name>/<tag>` and `/<number>` |
| Git-based | `/mnt/data/<name>` | `/mnt/data/snapshots/<name>/<tag>` and `/<number>` |
| Shared from another project (DFS) | `/domino/datasets/<name>` | `/domino/datasets/snapshots/<name>/<tag>` |
| Shared from another project (Git-based) | `/mnt/imported/data/<name>` | `/mnt/imported/data/snapshots/<name>/<tag>` |

```python
import pandas as pd
df = pd.read_parquet("/mnt/data/customer-features/features.parquet")              # live
df_v1 = pd.read_parquet("/mnt/data/snapshots/customer-features/v1.0/features.parquet")  # tag
```

The job object from [API-JOBS.md](./API-JOBS.md) lists the actual mounts under
`datasetMounts[].containerPath`.

## Uploading files

Writing to the mount path inside a Workspace or Job is the normal way to add data.
From outside an execution, python-domino `datasets_upload_files(dataset_id, local_path, ...)`
performs the chunked upload against the dataset files service
([SDK-EXAMPLES.md](./SDK-EXAMPLES.md#datasets)); the `/datasetrw/datasets/{datasetId}/snapshot/file/*`
routes it uses are in the spec but are a multi-step resumable protocol, so use the SDK
rather than calling them directly.

## python-domino

`datasets_list(project_id=None)`, `datasets_ids(project_id)`, `datasets_names(project_id)`,
`datasets_create(dataset_name, dataset_description)`, `datasets_details(dataset_id)`,
`datasets_update_details(dataset_id, dataset_name=None, dataset_description=None)`,
`datasets_remove(dataset_ids)`, `datasets_upload_files(...)`. There is no
`datasets_snapshot` or `datasets_tag`; use the REST routes above.

## Workflow example

```python
dataset = requests.post(f"{base_url}/api/datasetrw/v1/datasets", headers=headers,
                        json={"name": "feature-store", "projectId": project_id}).json()
dataset_id = dataset["id"] if "id" in dataset else dataset["dataset"]["id"]

# ... write files to the mount path inside a job, then:
snapshot = requests.post(f"{base_url}/api/datasetrw/v1/datasets/{dataset_id}/snapshots",
                         headers=headers, json={"relativeFilePaths": ["features.parquet"]}).json()
snapshot_id = snapshot["id"] if "id" in snapshot else snapshot["snapshot"]["id"]

requests.post(f"{base_url}/api/datasetrw/v1/datasets/{dataset_id}/tags", headers=headers,
              json={"snapshotId": snapshot_id, "tagName": "baseline"})
requests.post(f"{base_url}/api/datasetrw/v1/datasets/{dataset_id}/grants", headers=headers,
              json={"targetId": colleague_user_id, "targetRole": "DatasetRwReader"})
```

Check the create responses once on your deployment: v1 routes may return the object bare
or wrapped under `dataset` / `snapshot`.
