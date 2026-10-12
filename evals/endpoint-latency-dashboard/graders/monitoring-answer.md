---
type: llm
---

PASS if the reply points the user at the endpoint's own monitoring in Domino (the endpoint page's performance metrics, status codes, health checks and logs, which every user can see) and, for detailed dashboards and alerting, says that the Grafana dashboards and alert configuration are for Domino administrators (so a non-admin works with their admin or IT team on alert thresholds).
FAIL if it only gives REST deployment automation, tells a non-admin to build Grafana alerts themselves without noting the admin requirement, or invents Kubernetes autoscaling as the fix.
