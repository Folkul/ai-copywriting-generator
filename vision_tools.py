"""图片理解（千问 VL，支持 1～9 张）；文案从 llm 导出。"""
from __future__ import annotations

import base64
import os
from typing import Callable, Optional, Union

import dashscope

from config import MAX_IMAGE_BYTES, MAX_IMAGES, QWEN_API_KEY, QWEN_VL_MODEL

dashscope.api_key = QWEN_API_KEY

# #region agent log
def _agent_debug_log(location: str, message: str, data: dict, hypothesis_id: str = "") -> None:
    try:
        import json
        import time
        from pathlib import Path

        p = Path(__file__).resolve().parent / "debug-cadaef.log"
        line = {
            "sessionId": "cadaef",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "hypothesisId": hypothesis_id,
            "data": data,
        }
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass


# #endregion

from llm.caption import generate_caption  # noqa: E402

__all__ = [
    "encode_image_to_base64",
    "get_image_description",
    "generate_caption",
]


def _say(msg: str, verbose: bool, log: Optional[Callable[[str], None]]) -> None:
    if log:
        log(msg)
    elif verbose:
        print(msg)


def encode_image_to_base64(
    image_path: str,
    *,
    verbose: bool = True,
    log: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """将本地图片转为 base64 字符串。"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except FileNotFoundError:
        _say(f"错误：图片文件不存在 — {image_path}", verbose, log)
        return None
    except OSError as e:
        _say(f"错误：无法读取图片 — {e}", verbose, log)
        return None


def _guess_image_mime(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1].lower()
    if ext in (".png",):
        return "image/png"
    if ext in (".webp",):
        return "image/webp"
    if ext in (".gif",):
        return "image/gif"
    return "image/jpeg"


def _normalize_paths(
    image_paths: Union[str, list[str]],
    *,
    verbose: bool = True,
    log: Optional[Callable[[str], None]] = None,
) -> Optional[list[str]]:
    if isinstance(image_paths, str):
        paths = [image_paths]
    else:
        paths = list(image_paths)
    if not paths:
        _say("错误：至少提供一张图片。", verbose, log)
        return None
    if len(paths) > MAX_IMAGES:
        _say(f"错误：最多 {MAX_IMAGES} 张图片，当前 {len(paths)} 张。", verbose, log)
        return None
    return paths


def get_image_description(
    image_paths: Union[str, list[str]],
    *,
    verbose: bool = True,
    log: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """
    调用千问 VL。可传入单张路径字符串，或 1～9 张路径的列表。
    verbose=False 时不向 stdout 打印（供 Web 使用）；可传 log 回调收集信息。
    """
    if not QWEN_API_KEY:
        # #region agent log
        _agent_debug_log(
            "vision_tools.py:get_image_description",
            "empty QWEN_API_KEY",
            {"n_paths_hint": str(type(image_paths).__name__)},
            "H2",
        )
        # #endregion
        _say("错误：未配置 QWEN_API_KEY，请在 .env 中设置。", verbose, log)
        return None

    paths = _normalize_paths(image_paths, verbose=verbose, log=log)
    if not paths:
        return None

    for p in paths:
        try:
            size = os.path.getsize(p)
        except OSError as e:
            _say(f"错误：无法读取图片信息 — {p} — {e}", verbose, log)
            return None
        if size > MAX_IMAGE_BYTES:
            mb = MAX_IMAGE_BYTES // (1024 * 1024)
            _say(f"错误：图片过大 — {p}（{size} 字节），请压缩到约 {mb}MB 以内。", verbose, log)
            return None

    n = len(paths)
    _say(f"正在分析 {n} 张图片: {', '.join(paths)}...", verbose, log)

    content: list[dict[str, str]] = []
    for p in paths:
        b64 = encode_image_to_base64(p, verbose=verbose, log=log)
        if not b64:
            return None
        mime = _guess_image_mime(p)
        content.append({"image": f"data:{mime};base64,{b64}"})

    if n == 1:
        text_q = (
            "请用一到两句话描述这张图片的主要内容，注意关键物体、场景和氛围，"
            "便于后续为朋友圈写配文。"
        )
    else:
        text_q = (
            f"以上是按顺序排列的 {n} 张照片。请综合这些画面，用两到四句话描述这组照片的整体内容、"
            "氛围以及照片之间可能的关系（例如同一天、同一场景、情绪递进等），"
            "便于用于朋友圈多图/九宫格配文的场景。"
        )
    content.append({"text": text_q})

    messages = [{"role": "user", "content": content}]

    # #region agent log
    _agent_debug_log(
        "vision_tools.py:before_vl_call",
        "calling VL",
        {"model": QWEN_VL_MODEL, "n_images": n, "key_len": len(QWEN_API_KEY)},
        "H3-H5",
    )
    # #endregion

    try:
        response = dashscope.MultiModalConversation.call(
            model=QWEN_VL_MODEL,
            messages=messages,
        )
    except Exception as e:  # noqa: BLE001
        # #region agent log
        _agent_debug_log(
            "vision_tools.py:vl_exception",
            str(e)[:300],
            {"exc_type": type(e).__name__},
            "H5",
        )
        # #endregion
        _say(f"图片分析失败：调用异常 — {e}", verbose, log)
        return None

    sc = getattr(response, "status_code", None)
    code = getattr(response, "code", None)
    msg = getattr(response, "message", None)
    # #region agent log
    _agent_debug_log(
        "vision_tools.py:vl_response_meta",
        "after VL call",
        {
            "status_code": sc,
            "code": code,
            "message": (str(msg)[:400] if msg is not None else None),
        },
        "H3-H4",
    )
    # #endregion

    if sc == 200:
        description = _extract_vl_text(response)
        if not description:
            # #region agent log
            _agent_debug_log(
                "vision_tools.py:extract_fail",
                "200 but no text",
                {"has_output": hasattr(response, "output")},
                "H4",
            )
            # #endregion
            _say("图片分析失败：返回格式异常 — 未能解析出文本。", verbose, log)
            return None
        # #region agent log
        _agent_debug_log(
            "vision_tools.py:success",
            "description ok",
            {"desc_len": len(description)},
            "H3",
        )
        # #endregion
        _say(f"AI图片描述: {description}", verbose, log)
        return description

    _say(f"图片分析失败: {code} — {msg}", verbose, log)
    return None


def _extract_vl_text(response: object) -> Optional[str]:
    """从千问 VL 响应中取出文本（兼容 content 为 list 或单段结构）。"""
    try:
        out = response.output  # type: ignore[union-attr]
        raw = out.choices[0].message.content  # type: ignore[union-attr]
    except (AttributeError, IndexError, TypeError):
        return None

    if isinstance(raw, str):
        return raw.strip() or None

    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict) and "text" in first:
            return str(first["text"]).strip() or None
        if isinstance(first, str):
            return first.strip() or None

    return None


if __name__ == "__main__":
    img_path = "test.jpg"
    desc = get_image_description(img_path)
    if desc:
        final_caption = generate_caption(
            desc,
            style="幽默风趣",
            length="不超过30字",
            use_emoji=True,
            use_punctuation=True,
        )
        print("\n--- 最终文案 ---")
        print(final_caption)
