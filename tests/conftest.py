"""pytest 共享夹具：构造 mock 模式的测试应用与 TestClient（隔离临时数据目录/DB）。"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # 允许未 editable 安装时直接跑测试
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from services.api.app import create_app  # noqa: E402
from services.api.config import Settings  # noqa: E402


def _settings(tmp_path: Path, run_mode: str = "mock", weights: str = "nope.pt") -> Settings:
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    return Settings(
        run_mode=run_mode,
        db_url=f"sqlite:///{data_root / 'test.db'}",
        data_root=data_root,
        weights_path=Path(weights),
        detector_device="",
        detector_conf=0.25,
    )


@pytest.fixture
def client(tmp_path):
    app = create_app(_settings(tmp_path, "mock"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def real_client(tmp_path):
    """real 模式但权重不存在 → 检测应报 MODEL_UNAVAILABLE，不回退 mock。"""
    app = create_app(_settings(tmp_path, "real", str(tmp_path / "missing_weights.pt")))
    with TestClient(app) as c:
        yield c


def png_bytes(width: int = 64, height: int = 48, color=(120, 160, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_png() -> bytes:
    return png_bytes()
