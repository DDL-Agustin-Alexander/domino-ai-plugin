#!/usr/bin/env bash
set -euo pipefail
cat > qa.py <<'EOF'
from openai import OpenAI

client = OpenAI()


def ask(q: str) -> str:
    r = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": q}])
    return r.choices[0].message.content


if __name__ == "__main__":
    print(ask("What is Domino?"))
EOF
