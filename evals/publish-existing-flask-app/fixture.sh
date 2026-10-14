#!/usr/bin/env bash
set -euo pipefail
cat > app.py <<'EOF'
from flask import Flask

app = Flask(__name__)


@app.route("/")
def index():
    return "hello"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
EOF
cat > requirements.txt <<'EOF'
flask
EOF
