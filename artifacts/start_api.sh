#!/usr/bin/env bash
# 启动后端 API（real 模式，真实 YOLOv10 权重），脱离会话后台运行并自检健康/能力。
cd /mnt/d/AstraDesk
export ASTRADESK_RUN_MODE=real
export ASTRADESK_YOLO_WEIGHTS=/mnt/d/AstraDesk/weights/yolov10n.pt
export ASTRADESK_DATA_ROOT=/mnt/d/AstraDesk/data
rm -f /tmp/astradesk_api.log
setsid nohup ~/venvs/astradesk/bin/python -m uvicorn services.api.app:app \
  --host 127.0.0.1 --port 8000 > /tmp/astradesk_api.log 2>&1 < /dev/null &
echo "STARTED_PID=$!"
sleep 7
echo "=== log tail ==="
tail -15 /tmp/astradesk_api.log
echo "=== health ==="
curl -s --noproxy '*' -m 5 http://127.0.0.1:8000/api/v1/health
echo
echo "=== capabilities ==="
curl -s --noproxy '*' -m 5 http://127.0.0.1:8000/api/v1/capabilities
echo
