# Domino Apps API (beta catalog)

Catalog of the `/api/apps/beta/apps` routes, verified against both published specs. For
the v1 publish chain (`/api/apps/v1/apps`, drafts, `createAndStart`, `liveSync`) and the
app lifecycle, use [domino-apps/API-APPS.md](../domino-apps/API-APPS.md); prefer v1 routes
for new automation. Product docs:
https://docs.domino.ai/cloud/platform-capabilities/features/apps.

## Authentication

Use the shared setup block (`base_url`, `headers`) from
[domino-api-intro](../domino-api-intro/SKILL.md#authentication).

## List apps

```
GET /api/apps/beta/apps
```

| Parameter | Notes |
|-----------|-------|
| `projectId`, `ownerId`, `publisherId`, `name` | Filters |
| `status` | One of the app statuses (`Queued`, `Scheduled`, `Pending`, `Preparing`, `Building`, `Pulling`, `Running`, `Serving`, `StopRequested`, `StopAndDiscardRequested`, `Stopping`, `Finishing`, ...) |
| `tagIds` | Repeatable taxonomy tag ids |
| `accessStatus` | `granted`, `pending`, `noAccess` |
| `configurationType` | `STANDARD` (default) or `AISYSTEM` |
| `includeTemplateApps`, `prioritizePinned` | boolean |
| `sortField` (`name`, `lastUpdated`, `status`, `views`, `lastViewed`, `published`), `sortOrder` (`asc`, `desc`) | |
| `limit`, `offset` | Pagination |

Response: `{"items": [...]}`. Each item has `id`, `name`, `description`, `project`
(`id`, `name`, `ownerUsername`, `projectType`), `publisher`, `entryPoint`, `url`,
`visibility`, `discoverable`, `mountDatasets`, `renderIFrame`, `currentVersion`
(`id`, `hardwareTierId`, `environmentId`, `resolvedCommits`, `currentInstance`, ...).

```python
apps = requests.get(f"{base_url}/api/apps/beta/apps", headers=headers,
                    params={"projectId": project_id, "limit": 20}).json()["items"]
for app in apps:
    print(app["name"], app["id"], app["url"])
```

## Create an app

```
POST /api/apps/beta/apps
```

Required: `name`, `projectId`, `visibility`, `version`. Optional: `entryPoint`
(default `app.sh`), `discoverable`, `mountDatasets`, `renderIFrame`, `sendNotifications`,
`iconId`, `configurationType`, `accessStatuses[]` (`userId`, `status` `ALLOWED` /
`DENIED` / `PENDING`).

`version` fields (none required by the schema): `hardwareTierId`, `environmentId`,
`environmentRevisionId`, `entryScript`, `gitRef` (`{"type": "head|commitId|branches|tags|custom", "value": "..."}`),
`dfsCommitId`, `externalVolumeMountIds`, `netAppVolumeIds`, `dataPlaneId`,
`autoscalingSpecification` (`enabled` required; `minReplicas`, `maxReplicas` 1 to 30,
CPU/memory targets, stabilization windows, `useSessionAffinity`), `bundleId`,
`extendedIdentityPropagationToAppsEnabled`, `vanityUrl`, `tags`.

```python
app = requests.post(f"{base_url}/api/apps/beta/apps", headers=headers, json={
    "name": "customer-insights",
    "projectId": project_id,
    "visibility": "GRANT_BASED",
    "entryPoint": "app.sh",
    "version": {"hardwareTierId": "small-k8s", "environmentId": env_id},
}).json()
```

`visibility` values are not enumerated in the beta schema; live deployments return
`GRANT_BASED` for shared apps. Check the v1 chain in
[domino-apps/API-APPS.md](../domino-apps/API-APPS.md) for the documented values.

## Get, update, delete

```
GET    /api/apps/beta/apps/{appId}
PATCH  /api/apps/beta/apps/{appId}        body: metadata fields such as name, description, discoverable
DELETE /api/apps/beta/apps/{appId}
```

## Versions

```
GET   /api/apps/beta/apps/{appId}/versions
POST  /api/apps/beta/apps/{appId}/versions                       body: the version object above
GET   /api/apps/beta/apps/{appId}/versions/{versionId}
PATCH /api/apps/beta/apps/{appId}/versions/{versionId}
POST  /api/apps/beta/apps/{appId}/versions/{versionId}/start
POST  /api/apps/beta/apps/{appId}/versions/{versionId}/stop
```

Use `start` and `stop` on a version to run or halt the app.

## Instances and logs

```
GET    /api/apps/beta/apps/{appId}/versions/{versionId}/instances
GET    /api/apps/beta/apps/{appId}/versions/{versionId}/instances/{instanceId}
DELETE /api/apps/beta/apps/{appId}/versions/{versionId}/instances/{instanceId}
GET    /api/apps/beta/apps/{appId}/versions/{versionId}/instances/{instanceId}/logs
GET    /api/apps/beta/apps/{appId}/versions/{versionId}/instances/{instanceId}/realTimeLogs
POST   /api/apps/beta/apps/{appId}/versions/{versionId}/instances/{instanceId}/views
```

```python
versions = requests.get(f"{base_url}/api/apps/beta/apps/{app_id}/versions", headers=headers).json()
version_id = versions["items"][0]["id"]
instances = requests.get(f"{base_url}/api/apps/beta/apps/{app_id}/versions/{version_id}/instances",
                         headers=headers).json()
instance_id = instances["items"][0]["id"]
logs = requests.get(
    f"{base_url}/api/apps/beta/apps/{app_id}/versions/{version_id}/instances/{instance_id}/logs",
    headers=headers)
print(logs.text)
```

Check the list envelope key (`items`) once on your deployment; beta list responses may
differ from v1.

## Thumbnail, views, vanity URLs, filters, access

```
GET, POST, DELETE /api/apps/beta/apps/{appId}/thumbnail;  GET .../thumbnail/metadata
GET /api/apps/beta/apps/{appId}/views?startTimestamp=&endTimestamp=&granularity=     (epoch ms; granularity default 86400000)
GET /api/apps/beta/apps/vanityUrls/{vanityUrl}
GET /api/apps/beta/apps/projectFilterOptions;  GET /api/apps/beta/apps/publisherFilterOptions
POST /api/apps/beta/apps/{appId}/access/requests
GET, PUT /api/apps/beta/apps/{appId}/roles        (Cloud only)
```

## Workflow: create, wait, read logs, stop

```python
import time

app = requests.post(f"{base_url}/api/apps/beta/apps", headers=headers, json={
    "name": "ml-dashboard", "projectId": project_id, "visibility": "GRANT_BASED",
    "version": {"hardwareTierId": "small-k8s", "environmentId": env_id},
}).json()
app_id = app["id"]
version_id = app["currentVersion"]["id"]

requests.post(f"{base_url}/api/apps/beta/apps/{app_id}/versions/{version_id}/start", headers=headers)

while True:
    current = requests.get(f"{base_url}/api/apps/beta/apps/{app_id}", headers=headers).json()
    status = current["currentVersion"]["currentInstance"]["status"] \
        if current.get("currentVersion", {}).get("currentInstance") else "Pending"
    if status in ("Running", "Serving"):
        print("App is up:", current["url"]); break
    if status in ("Failed", "Stopped"):
        print("App did not start:", status); break
    time.sleep(10)

requests.post(f"{base_url}/api/apps/beta/apps/{app_id}/versions/{version_id}/stop", headers=headers)
```

## App requirements

Apps need an `app.sh` entry point that binds to `0.0.0.0:8888`; see
[domino-apps](../domino-apps/SKILL.md) for framework-specific scripts and proxy rules.
