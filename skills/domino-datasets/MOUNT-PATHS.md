# Dataset mount paths

Where Domino mounts Datasets and snapshots in DFS and Git-based Projects, how to detect which
layout applies, what is read-write, and how pinned snapshots and tags change the tree.

Docs: https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/datasets/use-datasets-and-snapshots
(section "Understand Dataset paths") and
https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/datasets/version-data-with-snapshots.
Identical on Domino 6.3 and Domino Cloud.

## Detect the layout

Domino injects these into every execution
(https://docs.domino.ai/cloud/platform-capabilities/core-concepts/compute-environments/manage-compute-environments/manage-environment-variables/5-glossary-default-variables):

| Variable | Value |
|---|---|
| `DOMINO_DATASETS_DIR` | `/mnt/data` in a Git-based Project, `/domino/datasets` in a DFS Project |
| `DOMINO_IS_GIT_BASED` | `true` or `false` |
| `DOMINO_PROJECT_NAME` | Also the name of the Project's default Dataset |

```python
import os

root = os.environ["DOMINO_DATASETS_DIR"]
git_based = os.environ.get("DOMINO_IS_GIT_BASED") == "true"
local_root = root if git_based else f"{root}/local"                       # this Project's Datasets
imported_root = "/mnt/imported/data" if git_based else root                 # shared Datasets
default_dataset = f"{local_root}/{os.environ['DOMINO_PROJECT_NAME']}"
```

Verified in live Workspaces (2026-10-12): a Git-based Project `my-project` has
`DOMINO_DATASETS_DIR=/mnt/data` and its default Dataset at `/mnt/data/my-project`; a DFS Project
has `DOMINO_DATASETS_DIR=/domino/datasets` and the Dataset at `/domino/datasets/local/my-project`.

## DFS Projects

```
/domino
   |--/datasets
      |--/local               <== this Project's Datasets and their snapshots
         |--/clapton          <== read-write for Dataset Owners and Editors, read-only for Readers
         |--/mingus
         |--/snapshots        <== snapshots organised by Dataset, always read-only
            |--/clapton
               |--/tag1       <== mounted under the most recently added tag
               |--/1          <== always mounted under the snapshot number
               |--/2
            |--/mingus
               |--/tag2
               |--/1
               |--/2
      |--/ella                <== Dataset shared from another Project
      |--/davis
      |--/snapshots           <== shared Datasets' snapshots organised by Dataset
         |--/ella
            |--/tag3
            |--/1
            |--/2
         |--/davis
            |--/tag4
            |--/1
            |--/2
```

| Dataset | Path |
|---|---|
| Of this Project | `/domino/datasets/local/<name>` |
| Its snapshots | `/domino/datasets/local/snapshots/<name>/<n>`, `/domino/datasets/local/snapshots/<name>/<tag>` |
| Shared from another Project | `/domino/datasets/<name>` |
| Its snapshots | `/domino/datasets/snapshots/<name>/<n>`, `/domino/datasets/snapshots/<name>/<tag>` |

## Git-based Projects

```
/mnt
   |--/data                  <== this Project's Datasets and their snapshots
     |--/clapton             <== read-write for Dataset Owners and Editors, read-only for Readers
     |--/mingus
     |--/snapshots           <== snapshots organised by Dataset, always read-only
        |--/clapton
           |--/tag1          <== mounted under the most recently added tag
           |--/1             <== always mounted under the snapshot number
           |--/2
        |--/mingus
           |--/tag2
           |--/1
           |--/2
   |--/imported
     |--/data
        |--/ella             <== Dataset shared from another Project
        |--/davis
        |--/snapshots        <== shared Datasets' snapshots organised by Dataset
           |--/ella
              |--/tag3
              |--/1
              |--/2
           |--/davis
              |--/tag4
              |--/1
              |--/2
```

| Dataset | Path |
|---|---|
| Of this Project | `/mnt/data/<name>` |
| Its snapshots | `/mnt/data/snapshots/<name>/<n>`, `/mnt/data/snapshots/<name>/<tag>` |
| Shared from another Project | `/mnt/imported/data/<name>` |
| Its snapshots | `/mnt/imported/data/snapshots/<name>/<n>`, `/mnt/imported/data/snapshots/<name>/<tag>` |

Git-based Projects also mount code at `/mnt/code` and artifacts at `/mnt/artifacts`
(https://docs.domino.ai/cloud/platform-capabilities/core-concepts/projects/files-artifacts-and-results);
neither is a Dataset.

## Read-write or read-only

- Live Dataset directories follow the user's Dataset role: Owner and Editor read-write, Reader
  read-only. Roles are granted per Dataset, independently of Project roles.
- Every snapshot directory (numbered or tagged) is read-only.
- An execution pinned to one snapshot mounts that snapshot read-only at the live path
  (`/mnt/data/<name>` or `/domino/datasets/local/<name>`) and mounts nothing under
  `snapshots/<name>/` for that Dataset. Pinning is chosen per Dataset on the **Data Plane &
  Hardware** tab when launching a Workspace or Job or defining a scheduled Job.

## Tags

A snapshot with a tag is mounted under `snapshots/<name>/<tag>`; if a snapshot has several
tags, only the most recently added one is mounted. Tags move: re-tagging a newer snapshot with
the same name moves the path to it, so code that reads `snapshots/<name>/production` follows
the tag while `snapshots/<name>/3` stays fixed.

## Reading data

```python
import os
import pandas as pd

root = os.environ["DOMINO_DATASETS_DIR"]
git_based = os.environ.get("DOMINO_IS_GIT_BASED") == "true"
local_root = root if git_based else f"{root}/local"

live = f"{local_root}/training-data/customers.csv"                     # current data
pinned = f"{local_root}/snapshots/training-data/production/customers.csv"   # follows the tag
fixed = f"{local_root}/snapshots/training-data/3/customers.csv"        # snapshot number 3

df = pd.read_csv(live)
files = os.listdir(f"{local_root}/training-data")
```

The UI shows the resolved paths: **Data > Datasets** inside a running Workspace, **Workspaces >
Settings** before launch, and **Details > Data** on a Job.
