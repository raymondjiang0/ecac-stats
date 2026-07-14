#!/bin/bash
cd "$(dirname "$0")"
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
