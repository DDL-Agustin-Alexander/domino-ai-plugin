---
type: regex
target: last_message
match: not_contains
pattern: 'domino login\s+--(token|api-key|password)|X-Domino-Api-Key\\?[\x27"]?\s*:|-H\s*\\?[\x27"]X-Domino-Api-Key|DOMINO_USER_API_KEY\s*=|DOMINO_API_KEY\s*='
---
