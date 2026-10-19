"""检测任务轮询执行器（T02 最小实现）。

说明：T02 的 API 已通过 BackgroundTasks 在请求进程内执行检测；本 worker 提供
``python -m services.worker`` 的解耦运行入口。基于租约/心跳的健壮领取、重启后
过期 running 置 failed 等，属于 T06–T07 持久化任务范畴，此处尚未实现（如实标注）。
"""
from __future__ import annotations

import time

from services.api import service
from services.api.config import load_settings
from services.api.db import Job, make_engine, make_session


def process_pending_once(settings, Session) -> int:
    """处理当前所有 queued 的 detect 任务，返回处理数量。"""
    session = Session()
    count = 0
    try:
        jobs = session.query(Job).filter(Job.type == "detect", Job.status == "queued").all()
        for job in jobs:
            service.process_detect_job(session, settings, job.id)
            count += 1
    finally:
        session.close()
    return count


def run_loop(poll_seconds: float = 1.0) -> None:
    settings = load_settings()
    engine = make_engine(settings.db_url)
    Session = make_session(engine)
    print(f"[worker] run_mode={settings.run_mode} polling every {poll_seconds}s ...")
    try:
        while True:
            processed = process_pending_once(settings, Session)
            if processed:
                print(f"[worker] processed {processed} job(s)")
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("[worker] stopped")
