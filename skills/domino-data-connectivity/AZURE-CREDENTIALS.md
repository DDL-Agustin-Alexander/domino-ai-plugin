# Azure Entra ID user-token propagation (blueprint)

Gives code running in a user's Workspace, Job or scheduled Job an OAuth access token for that
user's Entra ID (formerly Azure AD) identity, so Azure Storage, ADLS Gen2, Databricks, Azure SQL
and other Entra-protected services authorise and audit the individual user. There is no
product-side configuration file for this: it is a Keycloak configuration plus a small Python
package, published as a Professional Services blueprint.

- Blueprint: https://domino.ai/resources/blueprints/domino-azure-credential-propagation
- Code and setup guide: https://github.com/dominodatalab/domino-blueprints
  (`AD-User-README.md`, `advanced-credential-propagation/azure-ad-user-tokens/README.md`)
- Blueprints index on docs.domino.ai: https://docs.domino.ai/cloud/examples/blueprints

Applies to self-managed Domino 6.3, where your team administers Keycloak at
`https://<domino-domain>/auth/`. On Domino Cloud, request it through Domino Support. For
service (non-user) identities the blueprint README points to Azure Workload Identity instead;
it has no published guide.

Prefer the documented alternatives when they fit: an Azure Blob, ADLS or Databricks **Data
Source** (https://docs.domino.ai/cloud/platform-capabilities/core-concepts/data/data-source-connectors)
keeps a key or service principal in Domino's secret store and needs no Keycloak work.

## How it works

1. Keycloak (Domino's identity broker) is given an OIDC identity provider that points at an
   Entra application with the API permissions you want to delegate.
2. The first time a user asks for a token in a Workspace, the `domino_aad` package prints an
   Entra consent URL. After consent, Entra returns an access token and an offline refresh token;
   Keycloak stores the refresh token and the user never sees it.
3. On later calls, `domino_aad` performs a Keycloak internal-to-external token exchange and
   returns a fresh access token. Consent lasts as long as the refresh token, which the tenant
   controls; when it expires the user is prompted again.

## Setup (Keycloak and Entra admins)

### Entra application

Register (or reuse the SSO) application in the tenant. Under **API permissions**, add the
delegated permissions for each target service, for example `user_impersonation` on Azure
Storage (`https://storage.azure.com/`). Under **Authentication**, add the redirect URI that
Keycloak displays for the identity provider you create below.

### Keycloak identity provider

In the Keycloak admin console (**Domino Realm > Identity providers > Add provider > OpenID
Connect v1.0**):

1. In Entra, copy the application's **OpenID Connect metadata document** URL
   (**Overview > Endpoints**) and import it into the new provider.
2. Set **Client ID** and **Client secret** from the application. Store the secret in the
   Keycloak form only; never in code, notebooks or chat.
3. Enable **Store Tokens** and **Stored Tokens Readable**; set **First Login Flow** to
   `Domino First Broker Login`; turn **Account Linking Only** and **Disable user info** on.
4. Under **Mappers**, add an `Attribute Importer` mapping claim `email` to user attribute
   `email`.
5. Under **Default Scopes**, enter the scopes to request, for example
   `offline_access https://storage.azure.com/user_impersonation`. The second scope must match
   the API permission you granted; add one per target service.

### Token exchange permission

Follow the Keycloak guide for internal-to-external token exchange
(https://www.keycloak.org/docs/latest/securing_apps/#internal-token-to-external-token-exchange)
to allow the `domino-play` client to exchange tokens with the new identity provider; in the
client-policy step, `domino-play` is the client.

### Workload package

Install the exchange helper in the compute environment (Dockerfile) or the Workspace. The
blueprint distributes it as a wheel; take the current URL from the blueprint README:

```dockerfile
USER root
RUN python -m pip install https://mirrors.domino.tech/domino_aad-0.0.4-py3-none-any.whl
USER ubuntu
```

## Using it in a workload

`DominoCredential("<idp-alias>")` is an Azure `TokenCredential`; pass it wherever an Azure SDK
client takes `credential=`. The alias is the Keycloak identity-provider alias (`azstorage` in
the blueprint). On the first call it prints a consent URL; open it, grant access, return to the
Workspace and press Enter.

```python
from domino_aad import DominoCredential
from azure.storage.blob import BlobServiceClient

creds = DominoCredential("azstorage")
blob = BlobServiceClient("https://mystorageaccount.blob.core.windows.net", credential=creds)
for container in blob.list_containers(include_metadata=True):
    print(container["name"])
```

ADLS Gen2 and a pandas read:

```python
from io import StringIO
import pandas as pd
from azure.storage.filedatalake import DataLakeServiceClient

dl = DataLakeServiceClient("https://mystorageaccount.dfs.core.windows.net", credential=creds)
fs = dl.get_file_system_client("lake")
content = fs.get_file_client("sales/2026/sales.csv").download_file().readall().decode()
df = pd.read_csv(StringIO(content))
```

Azure SQL through pyodbc needs a token for the database scope; the Keycloak provider must
request that scope too (`https://database.windows.net/.default`):

```python
import struct
import pyodbc

token = creds.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
token_struct = struct.pack(f"<I{len(token)}s", len(token), token)
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=myserver.database.windows.net;DATABASE=mydb;",
    attrs_before={1256: token_struct},   # SQL_COPT_SS_ACCESS_TOKEN
)
```

`DefaultAzureCredential` does not find Domino-propagated tokens; use `DominoCredential`.

## Azure RBAC

Access on the Azure side is the user's own RBAC. Minimal roles for storage:

| Role | Permissions |
|---|---|
| Storage Blob Data Reader | Read blobs |
| Storage Blob Data Contributor | Read, write, delete blobs |
| Storage Blob Data Owner | Full access including POSIX ACLs |

```bash
az role assignment create \
  --role "Storage Blob Data Reader" \
  --assignee user@example.com \
  --scope /subscriptions/SUB_ID/resourceGroups/RG/providers/Microsoft.Storage/storageAccounts/ACCOUNT
```

Scope assignments to the storage account or container, enable Azure Monitor diagnostic
settings for audit, keep client-secret lifetimes short and apply Conditional Access policies.

## Troubleshooting

| Symptom | Check |
|---|---|
| Consent URL appears on every call | **Store Tokens** / **Stored Tokens Readable** off, or `offline_access` missing from the provider's default scopes |
| Token exchange denied | The `domino-play` client lacks the token-exchange permission for this provider |
| `AuthorizationPermissionMismatch` | The user's Azure RBAC role or scope; role propagation can take a few minutes |
| Wrong or missing scope in the token | The provider's **Default Scopes** and the application's API permissions must both include the target API |
| Token expired | Refresh token expired in the tenant; the user consents again |
