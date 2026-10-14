---
type: regex
target: { source: file, path: qa.py }
match: not_contains
pattern: 'Domino(Run|AgentContext)\(\s*run_name'
---
