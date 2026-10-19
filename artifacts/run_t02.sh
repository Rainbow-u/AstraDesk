#!/usr/bin/env bash
set -e
cd /mnt/d/AstraDesk
export YOLO_AUTOINSTALL=False
export ASTRADESK_RUN_MODE=real
timeout 240 ~/venvs/astradesk/bin/python artifacts/run_t02_real_detect.py 2>&1 | tail -50
echo "PIPE_EXIT=${PIPESTATUS[0]}"
