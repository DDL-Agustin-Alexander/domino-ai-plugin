---
type: llm
---

PASS if the Dockerfile instructions omit any `FROM` line (the base image is chosen in the environment's settings), switch to `USER root` before apt/pip installs and back to `USER ubuntu` afterwards, and the reply says the block goes into the environment's Dockerfile Instructions (Edit Definition) followed by a build / new revision.
FAIL if it includes a `FROM` line, ends as `USER domino`, or tells the user to put the packages only in requirements.txt as the permanent solution.
