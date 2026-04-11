"""上传图片魔数校验，避免非图文件占用 VL 额度。"""
from __future__ import annotations


def sniff_image_mime(data: bytes) -> tuple[str | None, str | None]:
    """
    返回 (mime, error)。
    WEBP 需前 12 字节含 WEBP 标记。
    """
    if len(data) < 12:
        return None, "文件过短，无法识别图片格式"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", None
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", None
    return None, "不支持的格式（请上传 JPG / PNG / GIF / WEBP）"
