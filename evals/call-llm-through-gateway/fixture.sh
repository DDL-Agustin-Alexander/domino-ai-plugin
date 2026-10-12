#!/usr/bin/env bash
set -euo pipefail
cat > ask.py <<'PY'
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def ask(question: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": question}],
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    print(ask("How do I reset my password?"))
PY
