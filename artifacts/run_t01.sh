#!/usr/bin/env bash
set -e
cd /mnt/d/AstraDesk
export YOLO_AUTOINSTALL=False
timeout 240 ~/venvs/astradesk/bin/python artifacts/run_t01_detection.py 2>&1 | tail -70
echo "PIPE_EXIT=${PIPESTATUS[0]}"
