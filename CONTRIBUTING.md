# Contributing to AutoBlog

Thanks for taking the time to contribute!

## Quick start (local dev)

### 1) Python environment

- Python: 3.10+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Build the sample site

```bash
python3 build.py
```

This generates output under `public/`.

### 3) Desktop App (optional)

```bash
pip install -r requirements.txt -r requirements_desktop.txt
python3 run_desktop.py
```

## What to contribute

- Fix bugs (repro steps + expected/actual behavior help a lot)
- Improve docs (README, examples, troubleshooting)
- Improve themes/templates

## Pull requests

- Keep changes focused and minimal.
- Add/update docs when behavior changes.
- If you change build output behavior, run `python3 build.py` before submitting.

## Reporting security issues

Please follow [SECURITY.md](SECURITY.md).
