#!/usr/bin/env bash
set -euo pipefail
cat > main.py <<'EOF'
from fastapi import FastAPI
from openai import OpenAI

app = FastAPI()
client = OpenAI()


@app.post("/chat")
def chat(body: dict):
    r = client.chat.completions.create(model="gpt-4o-mini", messages=body["messages"])
    return {"reply": r.choices[0].message.content}
EOF
cat > app.sh <<'EOF'
#!/bin/bash
uvicorn main:app --host 0.0.0.0 --port 8888
EOF
