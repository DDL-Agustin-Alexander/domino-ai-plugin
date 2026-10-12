---
name: domino-datasets
description: Work with Domino Datasets, the versioned filesystem storage mounted into Workspaces, Jobs, Apps and Launchers. Covers mount paths (/domino/datasets/local/<name> in DFS Projects, /mnt/data/<name> in Git-based Projects), creating and uploading (UI, domino upload-dataset), snapshots, tags and limits, sharing with Owner, Editor and Reader roles, and the /api/datasetrw REST routes. Use when storing or versioning data in Domino, reading a Dataset or snapshot from code, sharing data between Projects, or automating Dataset creation, snapshots and tags.
compatibility: Domino 6.3 and Domino Cloud. Requires DOMINO_API_HOST; in a run use DOMINO_API_PROXY or the localhost:8899 access-token endpoint, outside a run a Personal Access Token.
---

# Domino Datasets

Applies to Domino 6.3 and Domino Cloud.

A Dataset is Domino-managed, versioned filesystem storage. Executions mount it as an ordinary
directory: live data is read-write for Dataset Owners and Editors, read-only for Readers, and
every snapshot is a read-only directory beside it. Sharing is zero-copy; Domino sets no size or
file-count cap. For data beyond a few TB or already in object storage use a Data Source
(domino-data-sdk skill); for NetApp ONTAP storage see the netapp-volumes skill.

## Paths

| | DFS Project | Git-based Project |
|---|---|---|
| Dataset of this Project (RW) | `/domino/datasets/local/<name>` | `/mnt/data/<name>` |
| Its snapshots (RO) | `/domino/datasets/local/snapshots/<name>/<n>` and `/<tag>` | `/mnt/data/snapshots/<name>/<n>` and `/<tag>` |
| Dataset shared from another Project | `/domino/datasets/<name>` | `/mnt/imported/data/<name>` |
| Its snapshots (RO) | `/domino/datasets/snapshots/<name>/<n>` and `/<tag>` | `/mnt/imported/data/snapshots/<name>/<n>` and `/<tag>` |

`<n>` is the snapshot number, `<tag>` the most recently added tag. Every Project starts with a
default Dataset named after the Project: Project `churn` has `/mnt/data/churn` (Git-based) or
`/domino/datasets/local/churn` (DFS), both verified in live Workspaces. Detect the layout from
the injected variables, not by probing paths:

```python
import os
import pandas as pd

root = os.environ["DOMINO_DATASETS_DIR"]          # /mnt/data or /domino/datasets
git_based = os.environ.get("DOMINO_IS_GIT_BASED") == "true"
local = root if git_based else f"{root}/local"
df = pd.read_csv(f"{local}/{os.environ['DOMINO_PROJECT_NAME']}/raw/customers.csv")
```

Full trees, pinned snapshots, tags and read examples: [MOUNT-PATHS.md](./MOUNT-PATHS.md). The
UI lists mounted paths under **Data > Datasets** in a Workspace and **Details > Data** on a Job.

## Create a Dataset

- **UI**: in the Project, **Data > Domino Datasets > Create New Dataset**; name, description,
  then users or organizations with a Dataset role (or **Add all project members**), **Finish**.
- **REST**: `POST /api/datasetrw/v1/datasets` with
  `{"name": "...", "description": "...", "projectId": "<project-id>", "grants": []}`;
  `name` is required and unique in the Project; `snapshotId` instead of `projectId` copies a
  snapshot into a new Dataset. All routes, bodies and auth: [API.md](./API.md).
- **python-domino**: `Domino.datasets_create(dataset_name, dataset_description)` (positional
  names, not `name=`/`description=`); see the domino-python-sdk skill.

## Upload files

- **UI**: open the Dataset, **Upload files**: up to 50 GB or 50,000 files per upload;
  drag-and-drop keeps folder structure and can pause and resume.
- **CLI** (larger uploads): `domino upload-dataset [--fileUploadSetting Ignore|Overwrite|Rename]
  [--targetRelativePath <dir>] <owner>/<project>/<dataset> <local-folder>`; flags and values
  are case-sensitive; tune with `DOMINO_UPLOAD_CHUNK_BYTES` (default 3 MB) and
  `DOMINO_UPLOAD_THREADS` (default 8). Install: https://docs.domino.ai/cloud/reference/cli/install-the-cli
- **From code**: write to the mount path; every execution sees the change at once, and it
  becomes a version when you snapshot.
- **python-domino**: `datasets_upload_files(dataset_id, local_path_to_file_or_directory,
  file_upload_setting=None, max_workers=None, target_chunk_size=None, target_relative_path=None)`.

## Snapshots and tags

A snapshot is a read-only, immutable copy taken at a point in time. Do not modify files while
one is in progress; time scales with size.

- **Create**: UI **Take Snapshot** (all or selected files, optional tag);
  `domino create-snapshot <owner>/<project>/<dataset>`; or
  `POST /api/datasetrw/v1/datasets/{datasetId}/snapshots` with `{"relativeFilePaths": ["/*"]}`.
  `status` starts `pending` and becomes `active`; poll `GET /api/datasetrw/v1/snapshots/{id}`.
- **Read**: the numbered or tagged path above, or pin the execution to one snapshot on the
  **Data Plane & Hardware** tab at launch; it then mounts read-only at the live path.
- **Iterate**: snapshots never change. **Copy to New Dataset**, `POST .../datasets` with
  `snapshotId`, or `domino create-dataset-from-snapshot <owner>/<project>/<dataset> <n> <new-name>`.
- **Tags** name one snapshot (`snapshots/<name>/<tag>`); Owners and Editors add or remove them on
  the **Snapshots** page or with `POST .../datasets/{datasetId}/tags`
  `{"snapshotId": "...", "tagName": "production"}` and `DELETE .../tags/{tagName}`. To move a
  tag, remove it and add it to the newer snapshot.
- **Limits**: by default 20 active snapshots per Dataset (6.3 configuration record
  `com.cerebro.domino.dataset.quota.maxActiveSnapshotsPerDataset`; Domino Support on Cloud).
  At the limit an execution that would write a snapshot fails with an error; nothing is
  deleted on its own. Delete old snapshots, raise the limit, or exempt the Project; details in
  [BEST-PRACTICES.md](./BEST-PRACTICES.md).

## Share across Projects

Dataset roles are independent of Project roles: **Owner** (everything, including permissions),
**Editor** (upload, snapshot, tag, update metadata), **Reader** (view and mount). Grant them on
the Dataset's permissions panel or with `POST /api/datasetrw/v1/datasets/{datasetId}/grants`
(`DatasetRwOwner`, `DatasetRwEditor`, `DatasetRwReader`). A user with a role mounts the Dataset
in another Project via **Data > Domino Datasets > Mount Shared Dataset** or
`POST /api/projects/v1/projects/{projectId}/shared-datasets`; it appears under the imported
paths. Unmounting does not affect running executions.

Reads without a mount (Apps, endpoints, other Projects): `DatasetClient` in the domino-data-sdk
skill, read-only, with `DatasetConfig(snapshot_id=...)` for a snapshot.

## Delete

Owners mark a Dataset or snapshot for deletion (**More Actions > Delete Dataset**), which
removes it from new executions everywhere; an admin deletes it permanently.

## Troubleshooting

| Symptom | Check |
|---|---|
| Path missing in the execution | `DOMINO_IS_GIT_BASED`; Dataset mounted in this Project; execution started after the mount; not excluded on the launch form |
| Permission denied writing | Dataset role (Reader is read-only); snapshot and imported paths are read-only; a pinned snapshot replaces the live mount |
| Snapshot error at launch or `failed` status | Snapshot limit reached; delete snapshots or raise the limit |
| Slow reads | Parquet over CSV, read only needed columns, chunked or Dask reads ([BEST-PRACTICES.md](./BEST-PRACTICES.md)) |

## Reference files

- [MOUNT-PATHS.md](./MOUNT-PATHS.md): full DFS and Git-based trees, env-based detection, pinned snapshots, tags
- [API.md](./API.md): `/api/datasetrw` and shared-dataset routes with bodies, auth and examples
- [BEST-PRACTICES.md](./BEST-PRACTICES.md): what goes where, layout, formats, snapshot before change, large reads

Docs: https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/datasets (and its
child pages), https://docs.domino.ai/cloud/admin/data-administration/datasets,
https://docs.domino.ai/cloud/reference/cli/cli-reference; `/6.3/` for self-managed Domino 6.3.
