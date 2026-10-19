#!/usr/bin/env bash
# 小批量试跑(2 epoch)确认 6GB 显存余量；并行采样 nvidia-smi 峰值。日志落 /tmp/trial_desk_fine.log。
cd /mnt/d/AstraDesk
export YOLO_AUTOINSTALL=False
mkdir -p ~/.config/Ultralytics
if [ ! -f ~/.config/Ultralytics/Arial.ttf ]; then
  cp /mnt/c/Windows/Fonts/arial.ttf ~/.config/Ultralytics/Arial.ttf 2>/dev/null || true
fi
rm -f /tmp/trial_desk_fine.log /tmp/trial_mem.txt
# 后台显存采样：每 2s 记一次 memory.used(MiB)，共 120 次
( for i in $(seq 120); do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits >> /tmp/trial_mem.txt; sleep 2; done ) &
SAMPLER=$!
ASTRADESK_EPOCHS=2 ASTRADESK_TRIAL=1 ~/venvs/astradesk/bin/python tools/train_desk_fine.py > /tmp/trial_desk_fine.log 2>&1
kill $SAMPLER 2>/dev/null
PEAK=$(sort -n /tmp/trial_mem.txt | tail -1)
echo "TRIAL_PEAK_MEM_MiB=$PEAK"
echo "TRIAL_EXIT=$?"
