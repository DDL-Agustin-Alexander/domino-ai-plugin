---
type: regex
target: { source: file, path: .github/workflows/publish-domino-app.yml }
match: not_contains
pattern: 'X-Domino-Api-Key\\?[\x27"]?\s*:|-H\s*\\?[\x27"]X-Domino-Api-Key|DOMINO_USER_API_KEY\s*=|DOMINO_API_KEY\s*='
---
