"""worker 入口：``python -m services.worker``。"""
from __future__ import annotations

from .runner import run_loop

if __name__ == "__main__":
    run_loop()
