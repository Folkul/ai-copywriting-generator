"""从封面图提取主色与冷暖倾向，用于文案 prompt 中的 emoji 搭配建议（不展示色块）。"""
from __future__ import annotations

import colorsys
from typing import Literal

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

WarmthLabel = Literal["暖色调", "冷色调", "中性"]


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)


def _hue_warmth_score(h: float, s: float, v: float) -> float:
    """返回 [-1, 1]，越大越偏暖；低饱和度接近 0。"""
    if s < 0.12 or v < 0.08:
        return 0.0
    deg = h * 360.0
    # 红橙黄为暖，青蓝紫为冷
    if deg < 70 or deg >= 300:
        return 1.0
    if 160 <= deg < 280:
        return -1.0
    return 0.0


def extract_dominant_colors_and_warmth(
    image_path: str,
    *,
    resize: int = 150,
    n_clusters: int = 3,
    random_state: int = 42,
) -> tuple[list[tuple[int, int, int]], WarmthLabel]:
    """
    缩小图像后用 KMeans 提取 n_clusters 个主色（RGB），并判断整体偏暖/冷/中性。
    """
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        im = im.resize((resize, resize), Image.Resampling.LANCZOS)
        arr = np.asarray(im, dtype=np.float32).reshape(-1, 3)

    km = KMeans(n_clusters=n_clusters, n_init=10, random_state=random_state)
    labels = km.fit_predict(arr)
    centers = km.cluster_centers_
    counts = np.bincount(labels, minlength=n_clusters).astype(np.float64)
    weights = counts / (counts.sum() or 1.0)

    rgb_list: list[tuple[int, int, int]] = []
    weighted_scores: list[float] = []
    for i in range(n_clusters):
        r, g, b = centers[i]
        ri, gi, bi = int(round(r)), int(round(g)), int(round(b))
        ri = max(0, min(255, ri))
        gi = max(0, min(255, gi))
        bi = max(0, min(255, bi))
        rgb_list.append((ri, gi, bi))
        h, s, v = _rgb_to_hsv(ri, gi, bi)
        weighted_scores.append(_hue_warmth_score(h, s, v) * float(weights[i]))

    score = float(sum(weighted_scores))
    if score > 0.18:
        warmth: WarmthLabel = "暖色调"
    elif score < -0.18:
        warmth = "冷色调"
    else:
        warmth = "中性"

    return rgb_list, warmth


def build_emoji_tone_prompt_appendix(warmth: WarmthLabel) -> str:
    """构造追加到三条文案用户 prompt 末尾的 emoji 色调建议段落。"""
    if warmth == "暖色调":
        tone_zh = "暖色调"
        suggest = "暖色系 emoji 如 🌅🍁☀️🔥🧡"
    elif warmth == "冷色调":
        tone_zh = "冷色调"
        suggest = "冷色系 emoji 如 🌊🍃💙💜✨"
    else:
        tone_zh = "中性"
        suggest = "中性通用 emoji"
    return (
        f"【Emoji 色调搭配建议】用户上传图片的主色调为 {tone_zh}，建议优先选用 {suggest}。"
        "此条仅为创意建议，不必严格遵循。"
    )
