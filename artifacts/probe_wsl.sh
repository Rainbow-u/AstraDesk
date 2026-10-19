#!/usr/bin/env bash
echo "=== WSL OS ==="
lsb_release -d 2>/dev/null
uname -r
echo "=== python3 ==="
which python3 && python3 --version
echo "=== pip ==="
python3 -m pip --version 2>&1 | head -1
echo "=== venv ==="
python3 -c "import venv; print('venv ok')" 2>&1
echo "=== node ==="
which node 2>&1 && node --version 2>&1
echo "=== nvidia-smi in WSL ==="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>&1 | head -3
echo "=== nvcc ==="
nvcc --version 2>&1 | tail -2
echo "=== disk ==="
df -h / 2>/dev/null | tail -1
