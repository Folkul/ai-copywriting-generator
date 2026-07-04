"""Agent 轻量偏好记忆：本地 JSON 文件记录风格采纳/拒绝历史，生成时作为软参考喂给模型。

设计原则：
- 不做用户账号，不引入数据库，按浏览器/本地会话维度存储
- 历史信息以自然语言摘要形式注入 prompt，由模型自主判断是否延续
- 绝不用历史直接覆盖用户当前选择的风格参数
- 读取失败或文件损坏时静默降级，不影响生成流程
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from config import AGENT_MEMORY_ENABLED, AGENT_MEMORY_CONTEXT_ENTRIES, AGENT_MEMORY_MAX_ENTRIES, PROJECT_ROOT

# 历史文件路径
HISTORY_FILE = PROJECT_ROOT / "data" / "preference_history.json"

# 风格 slug → 中文显示名
_STYLE_DISPLAY_NAMES: dict[str, str] = {
    "humor": "幽默风趣",
    "literary": "文艺清新",
    "concise": "简洁干练",
    "lyrical": "歌词感",
    "daily_life": "生活随记",
    "travel": "旅行手记",
    "fun": "玩梗整活",
    "recommend": "种草安利",
}


def _ensure_dir() -> None:
    """确保 data 目录存在。"""
    d = HISTORY_FILE.parent
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def load_history() -> list[dict]:
    """从 JSON 文件加载全部历史记录；文件不存在或损坏时返回空列表。"""
    if not AGENT_MEMORY_ENABLED:
        return []
    try:
        if not HISTORY_FILE.is_file():
            return []
        text = HISTORY_FILE.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            # 过滤掉明显损坏的条目
            return [
                item
                for item in data
                if isinstance(item, dict)
                and "style" in item
                and "adopted" in item
                and isinstance(item["adopted"], bool)
            ]
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return []


def save_history(entries: list[dict]) -> bool:
    """将历史记录写入 JSON 文件（先写临时文件再替换，降低写坏风险）。"""
    if not AGENT_MEMORY_ENABLED:
        return False
    _ensure_dir()
    tmp = HISTORY_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(HISTORY_FILE)
        return True
    except OSError:
        return False


def record_feedback(style: str, adopted: bool) -> None:
    """追加一条反馈记录，自动裁剪到最近 N 条。"""
    if not AGENT_MEMORY_ENABLED:
        return
    style_clean = (style or "").strip()
    if not style_clean:
        return

    history = load_history()
    history.append(
        {
            "style": style_clean,
            "adopted": adopted,
            "timestamp": int(time.time()),
        }
    )
    # 只保留最近 N 条
    if len(history) > AGENT_MEMORY_MAX_ENTRIES:
        history = history[-AGENT_MEMORY_MAX_ENTRIES:]
    save_history(history)


def build_memory_context(max_entries: int | None = None) -> Optional[str]:
    """读取最近 N 条反馈记录，生成自然语言摘要供模型参考。

    返回 None 表示没有可用历史（无需注入 prompt）。
    返回的文本是「软参考」口吻，明确告诉模型这是偏好参考而非硬性规则。
    """
    if not AGENT_MEMORY_ENABLED:
        return None

    limit = max_entries if max_entries is not None else AGENT_MEMORY_CONTEXT_ENTRIES
    history = load_history()
    if not history:
        return None

    recent = history[-limit:]

    # 统计采纳/拒绝
    adopted_styles: dict[str, int] = {}
    rejected_styles: dict[str, int] = {}
    for entry in recent:
        s = entry.get("style", "")
        if entry.get("adopted"):
            adopted_styles[s] = adopted_styles.get(s, 0) + 1
        else:
            rejected_styles[s] = rejected_styles.get(s, 0) + 1

    # 构建偏好摘要
    parts: list[str] = []
    for style_slug, count in adopted_styles.items():
        display = _STYLE_DISPLAY_NAMES.get(style_slug, style_slug)
        parts.append(f"{count} 次采纳了「{display}」风格")
    for style_slug, count in rejected_styles.items():
        display = _STYLE_DISPLAY_NAMES.get(style_slug, style_slug)
        parts.append(f"{count} 次在「{display}」风格下选择了换三条")

    if not parts:
        return None

    summary = "、".join(parts)
    total = len(recent)

    return (
        f"【用户近期风格偏好参考】（仅供参考，非硬性要求）\n"
        f"以下是该用户最近 {total} 次生成中的偏好记录：{summary}。\n"
        f"你可以在生成时酌情参考以上偏好来微调文案的风格倾向，"
        f"但如果用户本次已通过风格参数、补充要求或其他方式明确指定了风格，"
        f"必须以用户本次的明确指定为准。以上偏好仅作为没有明确指示时的软性参考，"
        f"不要让它覆盖或替代用户当前的选择。"
    )


def get_memory_display_hint() -> Optional[dict]:
    """返回前端展示用的小提示信息（非 None 表示有可用记忆）。

    返回格式：{"summary": "...", "dominant_style": "humor", "adopted_ratio": "2/3"}
    """
    if not AGENT_MEMORY_ENABLED:
        return None

    history = load_history()
    if not history:
        return None

    recent = history[-AGENT_MEMORY_CONTEXT_ENTRIES:]

    # 统计
    style_counts: dict[str, dict[str, int]] = {}
    for entry in recent:
        s = entry.get("style", "")
        if s not in style_counts:
            style_counts[s] = {"adopted": 0, "rejected": 0}
        if entry.get("adopted"):
            style_counts[s]["adopted"] += 1
        else:
            style_counts[s]["rejected"] += 1

    total_adopted = sum(v["adopted"] for v in style_counts.values())
    total_all = len(recent)

    # 找最偏好的风格
    dominant = max(style_counts.items(), key=lambda kv: kv[1]["adopted"], default=(None, {}))
    dominant_slug = dominant[0]
    dominant_display = _STYLE_DISPLAY_NAMES.get(dominant_slug or "", dominant_slug or "")

    # 简短摘要
    adopted_parts = []
    for s, c in style_counts.items():
        if c["adopted"] > 0:
            display = _STYLE_DISPLAY_NAMES.get(s, s)
            adopted_parts.append(f"偏好{display}({c['adopted']}/{c['adopted']+c['rejected']})")

    return {
        "summary": "、".join(adopted_parts) if adopted_parts else "暂无明确偏好",
        "adopted_ratio": f"{total_adopted}/{total_all}",
        "dominant_style": dominant_slug,
        "dominant_display": dominant_display,
        "total_entries": total_all,
    }
