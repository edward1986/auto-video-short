# Technology Then vs Now — Kokoro Model Path Fix

This version fixes `Missing Kokoro model file: /home/runner/.cache/kokoro/...`.

The workflow sets `KOKORO_DIR` **once at job level** to `${{ runner.temp }}/kokoro-models`; every step uses that same directory. The Python generator also downloads and validates the model automatically if missing, to recover even when the cache is empty.

The download URLs use the official [kokoro-onnx model-files-v1.1](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1) release. Model filenames remain `kokoro-v1.0.int8.onnx` and `voices-v1.0.bin`.

## Install
Replace the files in your repo `Production` branch, keeping `.github/workflows/technology-then-now.yml` in its directory. Your existing YouTube OAuth secrets remain unchanged.

## Debug
In GitHub Actions, look for `Ensure Kokoro model files`. You should see `Saved ...` or `Kokoro cache OK`. Next, the video step will use precisely the same path.

Tested locally: Python syntax, workflow YAML parsing, model cache checks with test files. A live model download and video render were not performed in this environment.
