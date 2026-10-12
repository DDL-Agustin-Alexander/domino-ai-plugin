# The Domino R package

Sources: https://docs.domino.ai/cloud/reference/r-package/domino-r-package (6.3 page identical)
and the CRAN package source `domino_0.3.1.tar.gz` (published 2017-11-22, `NAMESPACE` and `R/`).
The product page itself says the information may be outdated and suggests writing your own R
wrapper around the platform API for anything more.

## What it is

A thin wrapper: every function builds a `domino --source R <command>` string and runs it with
`system()`. It finds the CLI on `PATH` or in the installer's default location
(`/Applications/domino/` on macOS, `~/domino/` on Linux, `C:\Program Files (x86)\domino\` on
Windows). The CLI must therefore be installed first ([CLI-INSTALL.md](./CLI-INSTALL.md)), and it
only does what the CLI does: file sync and runs on a Domino File System project. It does not call
the Domino REST API, so it knows nothing about Datasets commands added later, Git-based projects,
Model APIs or tokens.

## Install and load

```r
install.packages("domino", repos = "http://cran.r-project.org", type = "source")
library(domino)
```

## Sign in

Sign in from a terminal with the CLI (`domino login https://<your-domino-url>`, or
`domino login --device ...` without a local browser). The CLI keeps the session; R commands then
work.

`domino.login(usernameOrEmail, password, approvalForSendingErrorReports = FALSE, host)` pipes
`username`, `password` and a `Y`/`N` into `domino login <host>`'s legacy interactive prompt
(password prompted in RStudio or the console when omitted). The current CLI signs in through a
browser or device code, and no product page documents the username and password prompt any
more, so whether `domino.login()` still succeeds is unverified. Prefer the terminal login.

## Functions (all exported by `NAMESPACE`)

| Function | CLI command | Note |
|---|---|---|
| `domino.get(projectName)` | `get <projectName>` | `"owner/name"` or your own `"name"`; also `setwd()`s into the new folder |
| `domino.create(projectName)` | `create <projectName>` | new folder and project; `setwd()`s into it |
| `domino.init(projectName)` | `init <projectName>` | project rooted at the working directory; uploads nothing |
| `domino.run(..., publishApiEndpoint = FALSE)` | `run [--publish-api-endpoint] <file> <args>` | `domino.run("myScript.R", 1, "someString")`; arguments arrive as the script's command-line args |
| `domino.download()` | `download` | results and collaborators' changes into the project folder |
| `domino.upload(commitMessage)` | `upload [-m "<message>"]` | push without a run |
| `domino.sync()` | `sync` | download then upload |
| `domino.diff()` | `diff` | local versus last uploaded version |
| `domino.status(...)` | `status <args>` | current run status |
| `domino.reset()` | `reset` | reset the project in the working directory |
| `domino.debug()` | `--debug` | CLI debug information |
| `domino.dump()` | `dump` | CLI `dump` command |
| `domino.snapshot(commitMessage)` | `upload -m ...` after saving `snapshot_command_history.txt`, `snapshot_workspace.RData` and the current plot | one-call capture of the R session into the project |
| `domino.runCommand(commandAndArgs, successCallback, failureMessage, stdInput)` | any | run any CLI command string |

`diff`, `status`, `reset` and `dump` are not on the current CLI reference page; they come from the
2017 package and may no longer exist in the CLI. If one errors, use `domino help` to see what the
installed CLI offers.

All commands require the working directory to be inside a project folder (`.domino/` present);
`domino.get()` and `domino.create()` move you there.

## Typical session

```r
library(domino)
domino.get("quick-start")                 # ./quick-start, working directory changed
domino.run("myScript.R", 1, "someString") # starts a Job; returns at once with the run URL printed

for (alpha in 1:3) {                      # a small sweep: nine Jobs
  for (beta in 1:3) {
    domino.run("myScript.R", alpha, beta)
  }
}

domino.download()                         # once the runs finish
load("someData.RData")                    # results produced by the script
```

Inside `myScript.R`, read the arguments with `commandArgs(trailingOnly = TRUE)`.

## Calling the Domino API from R instead

For anything beyond file sync and runs (listing Jobs, Datasets, model serving), call the REST API
from R with `httr` and the same authentication rules as every other client
(https://docs.domino.ai/cloud/reference/api/domino-api-authentication):

```r
library(httr); library(jsonlite)

if (nzchar(Sys.getenv("DOMINO_API_PROXY"))) {                     # inside a Domino run
  base <- Sys.getenv("DOMINO_API_PROXY"); auth <- NULL
} else if (nzchar(Sys.getenv("DOMINO_API_HOST"))) {                # inside a run, no proxy
  tok  <- content(GET("http://localhost:8899/access-token"), as = "text")
  base <- Sys.getenv("DOMINO_API_HOST"); auth <- add_headers(Authorization = paste("Bearer", tok))
} else {                                                           # laptop: deployment URL and a Personal Access Token
  base <- "https://<deployment URL>"; auth <- add_headers(Authorization = paste("Bearer", Sys.getenv("DOMINO_PAT")))
}

r <- POST(paste0(base, "/api/jobs/v1/jobs"), auth, encode = "json",
          body = list(projectId = Sys.getenv("DOMINO_PROJECT_ID"), runCommand = "Rscript train.R"))
stop_for_status(r); fromJSON(content(r, as = "text"))$job$id
```

Routes: [domino-jobs](../domino-jobs/SKILL.md) and [domino-api-intro](../domino-api-intro/SKILL.md).
Never send `X-Domino-Api-Key`; legacy user API keys are deprecated.
