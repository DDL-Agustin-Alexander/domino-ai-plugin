---
type: llm
---

PASS if the reply (a) builds the launcher in the Domino UI with a command such as `python report.py --start-date ${start_date} --end-date ${end_date} --region ${region}`, (b) names the parameter controls Domino actually offers (Text, Select, Multi-select, Date, Checkbox, Upload files; naming at least three of these and none that Domino lacks), and (c) says results are delivered through the Job created by the run and the email notification (an `email.html` written by the script becomes the email body).
FAIL if it presents a YAML or JSON launcher definition file as something Domino reads, offers a "number" or "integer" parameter type, or runs the launcher through a `/v4/launchers/.../run` style REST call.
