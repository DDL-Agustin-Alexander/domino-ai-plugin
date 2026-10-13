---
type: regex
target: { source: file, path: experiment_setup.py }
match: not_contains
pattern: 'environ(\.get)?\(\s*[\x27"]DOMINO_HARDWARE_TIER_NAME|environ\[\s*[\x27"]DOMINO_HARDWARE_TIER_NAME|getenv\(\s*[\x27"]DOMINO_HARDWARE_TIER_NAME'
---
