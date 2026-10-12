---
type: llm
---

PASS if the reply (a) adds the EDV to the project under Data > External Data Volumes and reads it at `/domino/edv/lake-archive` in executions, and (b) for S3 offers credential-free or credential-managed paths such as a Domino S3 data source (queried through the Data API), AWS IRSA / credential propagation, or an admin-configured S3 mount, instead of embedding access keys in code.
FAIL if it tells the user to put AWS access keys in the script or gives `/mnt/external-data/...` as the EDV path.
