---
type: llm
---

PASS if the reply says the training data is registered as the model's training set / baseline through the endpoint's Monitoring setup in Domino (uploading or registering the training dataset), after which drift tests and thresholds are configured there, and describes the prediction capture as an edit to the prediction code (DataCaptureClient + capturePrediction).
FAIL if it claims predictions are captured automatically with no code change, or if it says captured predictions are read back from an invented local path as the mechanism.
