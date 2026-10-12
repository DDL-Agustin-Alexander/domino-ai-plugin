---
type: llm
---

PASS if the snapshot is taken from the dataset's page in the Domino UI, through `POST /api/datasetrw/v1/datasets/{datasetId}/snapshots`, or by setting `snapshotDatasetsOnCompletion` on the job, and the reply gives `/mnt/data/sales-raw` as the read-write path and `/mnt/data/snapshots/sales-raw/2` as the read-only snapshot path.
FAIL if it uses python-domino methods such as `datasets_snapshot` or `datasets_tag`, an `@tag` path syntax, or claims old snapshots are deleted automatically.
