---
type: regex
target: last_message
match: not_contains
pattern: 'jobs/v1/jobs/(\{[^}]+\}|\$\{?\w+\}?|[\x27"]\s*\+)(?!/tags)'
---
