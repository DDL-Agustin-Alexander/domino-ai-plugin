#!/usr/bin/env bash
set -euo pipefail
cat > predict.py <<'EOF'
import pickle

model = pickle.load(open('model.pkl', 'rb'))


def predict(sepal_length, sepal_width, petal_length, petal_width):
    pred = model.predict([[sepal_length, sepal_width, petal_length, petal_width]])[0]
    return {'variety': int(pred)}
EOF
: > model.pkl
