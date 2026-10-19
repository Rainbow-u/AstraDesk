"""图像上传预处理（PRD FR01）。

- 接受 JPEG / PNG；单张 ≤10MB 且解码 ≤2500 万像素。
- 校正 EXIF 方向；重存去除元数据，得到标准图 canonical。
- 拒绝伪装格式（magic bytes 与扩展名/声明不符）、损坏图、超限图。
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 25_000_000

_MAGIC = {
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
}


class PreprocessError(ValueError):
    """上传校验失败。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class CanonicalImage:
    """方向校正、去元数据后的标准图。"""

    image: Image.Image
    width: int
    height: int
    format: str  # "JPEG" 或 "PNG"


def _check_magic(raw: bytes, declared_ext: str) -> None:
    ext = (declared_ext or "").lower().lstrip(".")
    sigs = _MAGIC.get(ext)
    if sigs is None:
        raise PreprocessError("INVALID_IMAGE", f"unsupported extension: {ext!r}")
    if not raw.startswith(sigs):
        raise PreprocessError(
            "INVALID_IMAGE", "file magic bytes do not match declared extension"
        )


def preprocess(raw: bytes, declared_ext: str) -> CanonicalImage:
    """校验并生成标准图。失败抛 PreprocessError。"""
    if len(raw) > MAX_BYTES:
        raise PreprocessError("INVALID_IMAGE", "file exceeds 10MB")
    _check_magic(raw, declared_ext)

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise PreprocessError("INVALID_IMAGE", f"corrupt or undecodable image: {exc}")

    # EXIF 方向校正（去元数据的一部分）
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    if w * h > MAX_PIXELS:
        raise PreprocessError("INVALID_IMAGE", "image exceeds 25 megapixels")

    fmt = "PNG" if (declared_ext or "").lower().lstrip(".") == "png" else "JPEG"
    return CanonicalImage(image=img, width=w, height=h, format=fmt)


def to_bytes(canonical: CanonicalImage, quality: int = 90) -> bytes:
    """把标准图编码为字节（重存即剥离 EXIF/元数据）。"""
    buf = io.BytesIO()
    canonical.image.save(buf, format=canonical.format, quality=quality)
    return buf.getvalue()
