"""服务端文件存储（PRD 8.2：不接受客户端指定路径；图片路径由服务端生成）。

客户端只拿到 ``asset_id``，读取经 ``GET /assets/{id}`` 校验归属。
"""
from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

THUMB_MAX = 512


@dataclass
class StoredAsset:
    asset_id: str
    kind: str
    rel_path: str  # 相对项目根，正斜杠
    sha256: str
    width: int
    height: int


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def store_image(data_root: Path, project_id: str, kind: str, raw: bytes, ext: str) -> StoredAsset:
    """把图像字节写入 ``<data_root>/projects/<pid>/``，返回资产记录。路径由服务端生成。"""
    ext = ext.lstrip(".").lower()
    subdir = data_root / "projects" / project_id
    subdir.mkdir(parents=True, exist_ok=True)
    asset_id = uuid.uuid4().hex
    abs_path = subdir / f"{kind}_{asset_id}.{ext}"
    abs_path.write_bytes(raw)

    with Image.open(io.BytesIO(raw)) as im:
        w, h = im.size
    return StoredAsset(
        asset_id=asset_id,
        kind=kind,
        rel_path=str(abs_path).replace("\\", "/"),
        sha256=_sha256(raw),
        width=w,
        height=h,
    )


def make_thumbnail(data_root: Path, raw: bytes, project_id: str) -> StoredAsset:
    """生成缩略图（最长边 THUMB_MAX）并存储。"""
    with Image.open(io.BytesIO(raw)) as im:
        im.thumbnail((THUMB_MAX, THUMB_MAX))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=85)
        thumb_bytes = buf.getvalue()
    return store_image(data_root, project_id, "thumbnail", thumb_bytes, "jpg")
