#!/usr/bin/env bash
# T02 G0 验证：真实启动 uvicorn，探健康检查/能力/路由清单，然后停止。
cd /mnt/d/AstraDesk
export ASTRADESK_RUN_MODE=mock
export ASTRADESK_DATA_ROOT=/mnt/d/AstraDesk/artifacts/t02_api/data
mkdir -p "$ASTRADESK_DATA_ROOT"
PORT=8123
~/venvs/astradesk/bin/python -m uvicorn services.api.app:app --host 127.0.0.1 --port $PORT > /tmp/t02_api.log 2>&1 &
PID=$!
ok=0
for i in $(seq 1 30); do
  sleep 1
  if curl -s --noproxy '*' -m 3 http://127.0.0.1:$PORT/api/v1/health > /tmp/t02_health.json 2>/dev/null && [ -s /tmp/t02_health.json ]; then
    ok=1; break
  fi
done
echo "=== health (ok=$ok) ==="; cat /tmp/t02_health.json; echo
echo "=== capabilities ==="; curl -s --noproxy '*' -m 5 http://127.0.0.1:$PORT/api/v1/capabilities; echo
echo "=== openapi paths ==="
curl -s --noproxy '*' -m 5 http://127.0.0.1:$PORT/openapi.json | ~/venvs/astradesk/bin/python -c "import sys,json;print(sorted(json.load(sys.stdin)['paths'].keys()))"
echo "=== server log tail ==="; tail -6 /tmp/t02_api.log
kill $PID 2>/dev/null
sleep 1
echo "STOPPED"
