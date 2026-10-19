#!/usr/bin/env bash
# 脱离会话后台启动 desk9 微调，日志落 /tmp/train_desk9.log。
cd /mnt/d/AstraDesk
export YOLO_AUTOINSTALL=False
# 预置 Arial.ttf：github 被墙，ultralytics check_font 下载失败会硬崩训练；用 Windows 系统字体免联网。
mkdir -p ~/.config/Ultralytics
if [ ! -f ~/.config/Ultralytics/Arial.ttf ]; then
  cp /mnt/c/Windows/Fonts/arial.ttf ~/.config/Ultralytics/Arial.ttf 2>/dev/null || true
fi
rm -f /tmp/train_desk9.log
setsid nohup ~/venvs/astradesk/bin/python tools/train_desk9.py > /tmp/train_desk9.log 2>&1 < /dev/null &
echo "TRAIN_PID=$!"
