#!/bin/bash
export PYTHONPATH=$PYTHONPATH:.
source venv/bin/activate
python3 src/main.py "$@"
