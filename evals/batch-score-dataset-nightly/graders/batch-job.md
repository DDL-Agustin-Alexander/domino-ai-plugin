---
type: llm
---

PASS if the reply sets up a scoring script run as a Domino Job (reading the mounted dataset at its mount path and writing a predictions file), schedules it from Jobs > Schedules with a Quartz cron expression, and uses the scheduled Job's email notification (the files the Job creates are its results; an `email.html` can customise the message) to deliver the predictions.
FAIL if it deploys a Domino endpoint for the nightly scoring, or says scheduled Jobs can be created through the public REST API.
