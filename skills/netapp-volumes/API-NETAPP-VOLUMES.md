# NetApp Volumes REST API (`/remotefs/v1`)

Every route and body below is in both published Public API specs
(https://docs.domino.ai/api-specs/6.3/public-api.json and
https://docs.domino.ai/api-specs/cloud/public-api.json). The API page:
https://docs.domino.ai/cloud/reference/api/domino-volumes-api. Mount paths and in-run
file access: [DATA-ACCESS.md](./DATA-ACCESS.md).

## Authentication and base URL

Follow [domino-api-intro](../domino-api-intro/SKILL.md#authentication). For volume,
filesystem, snapshot and grant operations inside a run, use
`DOMINO_REMOTE_FILE_SYSTEM_HOSTPORT` when Domino injects it (the volumes API page says it
is for volume operations), otherwise `$DOMINO_API_PROXY` (no header) or `$DOMINO_API_HOST`
with the access token; outside Domino use the deployment URL with a PAT or service
account token. All examples share this setup:

```python
import os
import requests

if os.environ.get("DOMINO_API_PROXY"):
    base_url = os.environ["DOMINO_API_PROXY"].rstrip("/")
    headers = {}
elif os.environ.get("DOMINO_RUN_ID"):
    base_url = os.environ["DOMINO_API_HOST"].rstrip("/")
    token = requests.get("http://localhost:8899/access-token").text.strip()
    headers = {"Authorization": f"Bearer {token}"}
else:
    base_url = os.environ["DOMINO_API_HOST"].rstrip("/")          # deployment URL
    headers = {"Authorization": f"Bearer {os.environ['DOMINO_API_TOKEN']}"}

remotefs_url = os.environ.get("DOMINO_REMOTE_FILE_SYSTEM_HOSTPORT", base_url).rstrip("/")
```

Error bodies from this service are `{"message": "..."}`.

## Filesystems

```
GET  /remotefs/v1/filesystems?limit=&offset=&data_plane_id=
GET  /remotefs/v1/filesystems/{id}
POST /remotefs/v1/filesystems            admin: {"name", "dataPlaneId", "isDataPlaneDefault", "rootPvc", "storageClass", "maxSnapshotsPerVolume"}
PUT, DELETE /remotefs/v1/filesystems/{id}
```

```python
filesystems = requests.get(f"{remotefs_url}/remotefs/v1/filesystems", headers=headers).json()["data"]
for fs in filesystems:
    print(fs["id"], fs["name"], fs["dataPlaneName"], fs["numVolumes"], fs["maxSnapshotsPerVolume"])
```

Registering a filesystem is an administrator task that also needs Kubernetes and Trident
setup: https://docs.domino.ai/cloud/admin/data-administration/netapp-volumes.
`name`, `dataPlaneId`, `isDataPlaneDefault`, `rootPvc` and `storageClass` are required on
create.

## Create a volume

```
POST /remotefs/v1/volumes
```

Required: `name`, `filesystemId`, `capacity` (integer, bytes), `grants`
(`[{"targetId": "<user-or-org-id>", "targetRole": "VolumeOwner" | "VolumeEditor" | "VolumeReader"}]`).
Optional: `projectId` (attach on creation). There is no `description` field in the spec;
set the description in the UI.

```python
user_id = requests.get(f"{base_url}/api/users/v1/self", headers=headers).json()["user"]["id"]

volume = requests.post(f"{remotefs_url}/remotefs/v1/volumes", headers=headers, json={
    "name": "large-training-data",
    "filesystemId": filesystems[0]["id"],
    "capacity": 5_000_000_000_000,            # 5 TB in bytes
    "grants": [{"targetId": user_id, "targetRole": "VolumeOwner"}],
    "projectId": os.environ.get("DOMINO_PROJECT_ID"),
}).json()
print(volume["id"], volume["uniqueName"], volume["status"])
```

The volume record: `id`, `name`, `uniqueName`, `description`, `filesystemId`,
`filesystemName`, `capacity`, `storageSize`, `path`, `status` (`Active`,
`MarkedForDeletion`, `Deleted`), `numSnapshots`, `maxSnapshots`, `dataPlaneId`,
`grants[]` (`targetId`, `targetName`, `targetRole`, `isOrganization`), `projects[]`,
`createdAt`, `createdBy`, `updatedAt`, `updatedBy`, `taxonomyTags`, `properties`.

## Rename, attach, detach, delete

```
PATCH /remotefs/v1/volumes/{id}                          body: {"name": "new-name"}   (changes the mount path)
POST  /remotefs/v1/rpc/attach-volume-to-project          body: {"projectId": "...", "volumeId": "..."}   -> 204
POST  /remotefs/v1/rpc/detach-volume-from-project        body: {"projectId": "...", "volumeId": "..."}   -> 204
POST  /remotefs/v1/rpc/mark-volume-for-deletion          body: {"volumeId": "..."}   -> 204 (status MarkedForDeletion)
POST  /remotefs/v1/rpc/restore-volume                    body: {"volumeId": "..."}   (undo mark-for-deletion)
POST  /remotefs/v1/rpc/delete-volume                     body: {"volumeId": "..."}   (permanent; needs delete permission)
POST  /remotefs/v1/rpc/bulk-attach-volumes-to-project, /rpc/bulk-copy-volumes-to-project
```

```python
requests.post(f"{remotefs_url}/remotefs/v1/rpc/attach-volume-to-project", headers=headers,
              json={"volumeId": volume["id"], "projectId": project_id})
```

## Grants

```
GET /remotefs/v1/volumes/{id}/grants
PUT /remotefs/v1/volumes/{id}/grants      body: a JSON array of {"targetId", "targetRole"} (replaces the grant list)
```

```python
requests.put(f"{remotefs_url}/remotefs/v1/volumes/{volume_id}/grants", headers=headers, json=[
    {"targetId": user_id, "targetRole": "VolumeOwner"},
    {"targetId": "<other-user-id>", "targetRole": "VolumeEditor"},
    {"targetId": "<org-id>", "targetRole": "VolumeReader"},
])
```

Keep an owner in the list; the body replaces all grants. `Service` is a fourth role value
reserved for Domino services.

## Snapshots

```
GET  /remotefs/v1/snapshots?volume_id=<id>&run_id=<runId>&limit=&offset=
GET  /remotefs/v1/snapshots/{id};  PUT /remotefs/v1/snapshots/{id}
POST /remotefs/v1/snapshots                          body: {"volumeId": "...", "tagNames": ["v2.0"]}   (tagNames optional)
POST /remotefs/v1/snapshots/{id}/tags                body: {"name": "production"}
DELETE /remotefs/v1/snapshots/{id}/tags/{name}
POST /remotefs/v1/rpc/create-snapshot-from-run       body: {"volumeId": "...", "runId": "...", "userId": "..."}   (all required)
POST /remotefs/v1/rpc/restore-snapshot               body: {"snapshotId": "..."}   -> 204
POST /remotefs/v1/rpc/delete-snapshot                body: {"snapshotId": "..."}
GET  /remotefs/v1/volumes/{id}/snapshots/{version}
```

Query filters on the snapshot list are snake_case (`volume_id`, `run_id`), unlike the
Nucleus routes. There is no `description` field on snapshot create in the spec; the
commit message is entered in the UI.

```python
snapshot = requests.post(f"{remotefs_url}/remotefs/v1/snapshots", headers=headers,
                         json={"volumeId": volume_id, "tagNames": ["v2.0"]}).json()
print(snapshot["id"], snapshot["version"], [t["name"] for t in snapshot.get("tags", [])])

requests.post(f"{remotefs_url}/remotefs/v1/snapshots/{snapshot['id']}/tags",
              headers=headers, json={"name": "production"})

requests.post(f"{remotefs_url}/remotefs/v1/rpc/create-snapshot-from-run", headers=headers,
              json={"volumeId": volume_id, "runId": os.environ["DOMINO_RUN_ID"], "userId": user_id})
```

Snapshot record: `id`, `volumeId`, `version` (the number used in `snapshots/<name>/<number>`
mount paths), `status`, `tags[]` (`name`, `addedAt`, `addedBy`), `labels`, `runId`,
`createdAt`, `createdBy`.

## List volumes

```
GET /remotefs/v1/volumes?limit=&offset=&search=&sort_by=&order=&project_id=&data_plane_id=&status=&tag_ids=&filter_strictly_by_volume_roles=
GET /remotefs/v1/volumes/{id}
GET /remotefs/v1/volumes/ids;  GET /remotefs/v1/volumes/unique-name/{uniqueName}
```

```python
volumes = requests.get(f"{remotefs_url}/remotefs/v1/volumes", headers=headers,
                       params={"project_id": project_id, "limit": 50}).json()
for v in volumes["data"]:
    print(f"{v['name']}  {v['capacity'] / 1e12:.1f} TB  snapshots={v['numSnapshots']}/{v['maxSnapshots']}  id={v['id']}")
print(volumes["meta"]["pagination"])
```

## Files

```
GET    /remotefs/v1/volumes/{id}/files?path=<subpath>            list
GET    /remotefs/v1/volumes/{id}/files/raw/{path}, /files/preview/{path}, /files/metadata, /files/recursive
PATCH, DELETE /remotefs/v1/volumes/{id}/files
POST   /remotefs/v1/volumes/{id}/uploads/start, /uploads, GET /uploads/status, /uploads/{uploadID}, /uploads/{uploadID}/complete
GET    /remotefs/v1/snapshots/{id}/files, /files/raw/{path}, /files/preview/{path}, /files/metadata, /files/recursive
```

File operations run on a different host than volume operations
(https://docs.domino.ai/6.3/reference/api/domino-volumes-api):

- Outside a Domino execution: prefix the path with `/webvfs` on the deployment URL, for
  example `GET https://<deployment>/webvfs/remotefs/v1/volumes/{id}/files?path=raw`.
- Inside an execution: call `http://data-webvfs-service.domino-compute:80` with the path
  exactly as above (no prefix).

Inside a Workspace or Job, reading and writing the mount path is simpler than the file API
([DATA-ACCESS.md](./DATA-ACCESS.md)).

## Mount volumes in a job

`POST /api/jobs/v1/jobs` (Nucleus base, not `remotefs_url`):

```python
requests.post(f"{base_url}/api/jobs/v1/jobs", headers=headers, json={
    "projectId": project_id,
    "runCommand": "python train.py",
    "hardwareTier": "small-k8s",                     # optional hardware tier id
    "netAppVolumeIds": [volume_id],
    "snapshotNetAppVolumesOnCompletion": True,       # snapshot every mounted volume when the job ends
})
```

Only `projectId` and `runCommand` are required; `environmentId` is optional. Full body:
[API-JOBS.md](../domino-python-sdk/API-JOBS.md#start-a-job). Workspace sessions take the
same ids as `netAppVolumeMounts` on
`POST /api/projects/v1/projects/{projectId}/workspaces/{workspaceId}/sessions`.

## Transfers and other routes

`GET, POST /remotefs/v1/data-transfers`, `/data-transfers/{id}`, `POST /remotefs/v1/downloads`,
`/rpc/download-archive`, `/rpc/get-volume-mounts`, `/rpc/check-is-over-limit`,
`/remotefs/v1/root-pvcs`, `/remotefs/v1/staging-volume` and the
`/remotefs/v1/account/authz/...` permission checks are in the spec; pull their schemas from
[API-SPECS.md](../domino-api-intro/API-SPECS.md) when needed.

## Spec discovery

Published specs: [API-SPECS.md](../domino-api-intro/API-SPECS.md). Your deployment's copy
of this service's document is `https://<domino-domain>/docs/openapi/data_remotefs_service-swagger.json`
(unauthenticated, from the `/docs` reference). Do not derive the deployment hostname from
a JWT; read `DOMINO_API_HOST` or use the URL you sign in at.
