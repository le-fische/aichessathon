#!/bin/bash
# Move to the project directory
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Run the python wrapper using the project's virtual environment directly.
# This avoids relying on 'uv' being in the system PATH, which GUI apps often don't have.
exec "$DIR/.venv/bin/python" uci_wrapper.py
