"""Agent 自评审：模型扮演审稿人对生成的三条候选文案打分，支持不达标自动重试。

设计原则：
- 评审失败或解析失败时优雅降级（返回 None，不影响主流程）
- 评审使用的后端与文案生成相同（通过 provider 参数选择）
- 评审温度设为较低值（0.3）以保证评分一致性
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional, Sequence

from config import (
    AGENT_REVIEW_ENABLED,
    AGENT_REVIEW_PASS_THRESHOLD,
    AGENT_REVIEW_SCORE_THRESHOLD,
    CAPTION_MAX_TOKENS,
)
from llm.caption import _resolve_backend
from llm.http_chat import post_chat_completion


@dataclass
class CandidateScore:
    """单条候选的评分结果。"""

    index: int  # 1-based
    safety: int = 0  # 避雷合规 0-10
    length: int = 0  # 字数合规 0-10
    quality: int = 0  # 质量创意 0-10
    diversity: int = 0  # 差异性 0-10
    comment: str = ""

    @property
    def average(self) -> float:
        return (self.safety + self.length + self.quality + self.diversity) / 4.0

    @property
    def passed(self) -> bool:
        """单条是否及格（平均分 >= 阈值）。"""
        return self.average >= AGENT_REVIEW_SCORE_THRESHOLD

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "safety": self.safety,
            "length": self.length,
            "quality": self.quality,
            "diversity": self.diversity,
            "average": round(self.average, 1),
            "passed": self.passed,
            "comment": self.comment,
        }


@dataclass
class ReviewResult:
    """一次评审的完整结果。"""

    scores: list[CandidateScore]
    summary: str = ""

    @property
    def pass_count(self) -> int:
        return sum(1 for s in self.scores if s.passed)

    @property
    def meets_threshold(self) -> bool:
        """是否达到全线通过门槛（及格数 >= 阈值）。"""
        return self.pass_count >= AGENT_REVIEW_PASS_THRESHOLD

    def to_dict(self) -> dict:
        return {
            "scores": [s.to_dict() for s in self.scores],
            "pass_count": self.pass_count,
            "threshold": AGENT_REVIEW_PASS_THRESHOLD,
            "score_threshold": AGENT_REVIEW_SCORE_THRESHOLD,
            "meets_threshold": self.meets_threshold,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# 评审提示词
# ---------------------------------------------------------------------------

# 语言代码 → 评审提示中的语言指令（与正文生成共用 OUTPUT_LANGUAGE_LABELS 的概念）
_REVIEW_LANG_INSTRUCTIONS: dict[str, str] = {
    "zh-Hans": "你的评审意见（comment 和 summary）请使用简体中文。",
    "zh-Hant": "你的评审意见（comment 和 summary）请使用繁体中文。",
    "en": "Write your review comments and summary in English.",
    "fr": "Rédigez vos commentaires et résumé en français.",
    "ja": "審査コメントとサマリーは日本語で記述してください。",
    "ko": "심사 의견과 요약은 한국어로 작성해 주세요.",
    "mix": "你的评审意见请使用简体中文（可自然夹杂英文）。",
}


def build_review_prompt(
    candidates: list[str],
    min_chars: int,
    max_chars: int,
    avoid_lexicon: Optional[Sequence[str]] = None,
    output_language: str = "zh-Hans",
    style: str = "",
) -> str:
    """构造评审提示词，让模型扮演审稿人打分。"""
    avoid_list = list(avoid_lexicon or [])
    avoid_str = "、".join(avoid_list[:30]) if avoid_list else "（无特殊避雷词）"
    more_count = f" …等共 {len(avoid_list)} 项" if len(avoid_list) > 30 else ""

    cand_lines = []
    for i, text in enumerate(candidates):
        cand_lines.append(f"候选{i + 1}：{text}  【字符数={len(text)}】")
    cand_block = "\n".join(cand_lines)

    style_desc = style if style else "不限"

    lang_inst = _REVIEW_LANG_INSTRUCTIONS.get(
        output_language, _REVIEW_LANG_INSTRUCTIONS["zh-Hans"]
    )

    return f"""你是一位严格、公正的社交媒体文案审稿人。请评审以下三条候选朋友圈文案。

【候选文案】
{cand_block}

【评审标准】
• 字数硬要求：每条正文必须在 {min_chars}～{max_chars} 个字符之间（按 Python len() 计数，含空格与 emoji）
• 避雷词（严禁出现）：{avoid_str}{more_count}
• 风格参考：{style_desc}

【打分维度（每项 0-10 分，整数）】
1. safety（避雷合规）：是否完全避开避雷词、无敏感擦边、无不安全表达
2. length（字数合规）：正文长度是否严格落在 {min_chars}～{max_chars} 区间
3. quality（质量创意）：是否自然流畅、有记忆点、符合朋友圈调性且不空洞
4. diversity（差异性贡献）：本条与另外两条相比，在角度/修辞/情绪/叙事重点上是否有明显区分（三条完全相同打 0，各自独立打 10）

{lang_inst}

【输出格式】严格输出一段合法 JSON（不要加 ``` 或任何解释文字）：
{{"scores":[{{"index":1,"safety":10,"length":8,"quality":7,"diversity":6,"comment":"点评"}},{{"index":2,"safety":9,"length":7,"quality":8,"diversity":6,"comment":"点评"}},{{"index":3,"safety":10,"length":9,"quality":6,"diversity":6,"comment":"点评"}}],"summary":"整体评价，一句话"}}"""


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------

def parse_review_result(raw: str, *, verbose: bool = False) -> Optional[ReviewResult]:
    """从模型返回的原始文本中解析 ReviewResult；解析失败返回 None。"""
    if not raw:
        return None

    data: Optional[dict] = None

    # 1) 直接尝试 JSON 解析
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # 2) 尝试提取 JSON 对象
    if data is None:
        m = re.search(r'\{[^{}]*"scores"\s*:\s*\[.*?\][^{}]*\}', raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                pass

    if not data or not isinstance(data, dict) or "scores" not in data:
        if verbose:
            print("[Agent Review] 无法解析评审结果 JSON，降级跳过。")
        return None

    scores: list[CandidateScore] = []
    for item in data.get("scores", []):
        if not isinstance(item, dict):
            continue
        idx = item.get("index", 0)
        if not isinstance(idx, int) or idx < 1 or idx > 3:
            continue
        scores.append(
            CandidateScore(
                index=idx,
                safety=_clamp_score(item.get("safety", 0)),
                length=_clamp_score(item.get("length", 0)),
                quality=_clamp_score(item.get("quality", 0)),
                diversity=_clamp_score(item.get("diversity", 0)),
                comment=str(item.get("comment", ""))[:200],
            )
        )

    if len(scores) < 3:
        if verbose:
            print(f"[Agent Review] 仅解析到 {len(scores)} 条评分，不完整，降级跳过。")
        return None

    # 按 index 排序
    scores.sort(key=lambda s: s.index)
    # 确保 index 连续
    for i, s in enumerate(scores):
        s.index = i + 1

    return ReviewResult(
        scores=scores[:3],
        summary=str(data.get("summary", ""))[:300],
    )


def _clamp_score(val: object) -> int:
    """将评分限制在 0-10 的整数。"""
    try:
        v = int(float(str(val)))
    except (ValueError, TypeError):
        return 0
    return max(0, min(10, v))


# ---------------------------------------------------------------------------
# 评审入口
# ---------------------------------------------------------------------------

def review_candidates(
    candidates: list[str],
    min_chars: int,
    max_chars: int,
    avoid_lexicon: Optional[Sequence[str]] = None,
    output_language: str = "zh-Hans",
    style: str = "",
    provider: Optional[str] = None,
    verbose: bool = False,
) -> Optional[str]:
    """调用 LLM 对三条候选进行评审，返回原始响应文本。

    如果评审未启用、候选不足 3 条或后端不可用，返回 None。
    调用方应使用 parse_review_result() 解析返回值。
    """
    if not AGENT_REVIEW_ENABLED:
        if verbose:
            print("[Agent Review] 评审未启用（AGENT_REVIEW_ENABLED=false），跳过。")
        return None

    if len(candidates) < 3:
        if verbose:
            print("[Agent Review] 候选不足 3 条，跳过评审。")
        return None

    backend, err = _resolve_backend(provider)
    if not backend:
        if verbose:
            print(f"[Agent Review] 后端不可用，跳过：{err}")
        return None

    prompt = build_review_prompt(
        candidates,
        min_chars,
        max_chars,
        avoid_lexicon,
        output_language,
        style,
    )

    if verbose:
        print("[Agent Review] 正在调用模型评审三条候选…")

    result = post_chat_completion(
        backend.url,
        backend.api_key,
        backend.model,
        prompt,
        temperature=0.3,  # 低温度保证评审一致性
        max_tokens=min(CAPTION_MAX_TOKENS, 600),
        verbose=verbose,
    )

    if verbose and result:
        print("[Agent Review] 评审调用完成。")

    return result
