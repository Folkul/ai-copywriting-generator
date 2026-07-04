"""朋友圈文案：DeepSeek 或通义千问文本。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from config import (
    CAPTION_MAX_TOKENS,
    CAPTION_PROVIDER,
    DEEPSEEK_API_KEY,
    DEEPSEEK_CHAT_MODEL,
    DEEPSEEK_CHAT_URL,
    QWEN_API_KEY,
    QWEN_COMPAT_CHAT_URL,
    QWEN_TEXT_MODEL,
)
from llm.http_chat import post_chat_completion
from prompts import build_moments_caption_user_prompt, build_triple_caption_user_prompt


@dataclass(frozen=True)
class CaptionBackend:
    label: str
    url: str
    model: str
    api_key: str

    def is_configured(self) -> bool:
        return bool(self.api_key)


def _normalize_provider(name: Optional[str]) -> str:
    raw = (name or CAPTION_PROVIDER or "deepseek").strip().lower()
    aliases = {"通义": "qwen", "千问": "qwen", "qwen-turbo": "qwen"}
    return aliases.get(raw, raw)


def _backends() -> dict[str, CaptionBackend]:
    return {
        "deepseek": CaptionBackend(
            "DeepSeek",
            DEEPSEEK_CHAT_URL,
            DEEPSEEK_CHAT_MODEL,
            DEEPSEEK_API_KEY,
        ),
        "qwen": CaptionBackend(
            "通义千问（兼容模式）",
            QWEN_COMPAT_CHAT_URL,
            QWEN_TEXT_MODEL,
            QWEN_API_KEY,
        ),
    }


def list_caption_providers() -> list[str]:
    return sorted(_backends().keys())


def describe_caption_providers() -> list[tuple[str, str, bool]]:
    out: list[tuple[str, str, bool]] = []
    for pid, b in sorted(_backends().items(), key=lambda x: x[0]):
        out.append((pid, b.label, b.is_configured()))
    return out


def _resolve_backend(provider: Optional[str]) -> tuple[Optional[CaptionBackend], Optional[str]]:
    """返回 (backend, error_message)。"""
    pid = _normalize_provider(provider)
    backends = _backends()
    backend = backends.get(pid)
    if not backend:
        known = ", ".join(sorted(backends))
        return None, f"未知文案后端「{pid}」。可选：{known}"
    if not backend.is_configured():
        key_hint = {"deepseek": "DEEPSEEK_API_KEY", "qwen": "QWEN_API_KEY"}[pid]
        return None, f"未配置 {key_hint}，无法使用「{backend.label}」。"
    return backend, None


def generate_caption(
    description: str,
    style: str = "文艺青年",
    length: str = "约50字",
    elements: Optional[list[str]] = None,
    temperature: float = 0.8,
    provider: Optional[str] = None,
    *,
    use_emoji: bool = True,
    use_punctuation: bool = True,
    supplement: Optional[str] = None,
    output_language: str = "zh-Hans",
    avoid_lexicon: Optional[Sequence[str]] = None,
    verbose: bool = True,
) -> Optional[str]:
    """根据图片描述生成单条朋友圈文案。"""
    if not description:
        if verbose:
            print("错误：没有图片描述，无法生成文案。")
        return None

    backend, err = _resolve_backend(provider)
    if not backend:
        if verbose:
            print(f"错误：{err}")
        return None

    if verbose:
        print(f"正在生成风格为「{style}」的文案（{backend.label}）...")
    prompt = build_moments_caption_user_prompt(
        description,
        style=style,
        length=length,
        elements=elements,
        use_emoji=use_emoji,
        use_punctuation=use_punctuation,
        supplement=supplement,
        output_language=output_language,
        avoid_lexicon=list(avoid_lexicon) if avoid_lexicon else None,
    )
    text = post_chat_completion(
        backend.url,
        backend.api_key,
        backend.model,
        prompt,
        temperature,
        max_tokens=CAPTION_MAX_TOKENS,
        verbose=verbose,
    )
    if text and verbose:
        print("文案生成成功。")
    return text


def parse_three_candidates(raw: str) -> list[str]:
    """从模型输出中解析三条正文（去掉「候选n：」前缀）。"""
    if not raw:
        return []
    found: list[tuple[int, str]] = []
    for m in re.finditer(
        r"候选\s*([123一二三])\s*[:：]\s*(.+?)(?=\s*候选\s*[123一二三]\s*[:：]|\Z)",
        raw,
        flags=re.DOTALL,
    ):
        idx_map = {"1": 1, "2": 2, "3": 3, "一": 1, "二": 2, "三": 3}
        key = m.group(1)
        n = idx_map.get(key, 0)
        body = m.group(2).strip().replace("\r", "")
        # 去掉尾部多余空行
        body = body.split("\n")[0] if body else ""
        if n and body:
            found.append((n, body))
    found.sort(key=lambda x: x[0])
    out = [t[1] for t in found]
    if len(out) >= 3:
        return out[:3]

    # 回退：按行找「候选1：」形式
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    alt: list[str] = []
    for ln in lines:
        mm = re.match(r"^候选\s*[123一二三]\s*[:：]\s*(.+)$", ln)
        if mm:
            alt.append(mm.group(1).strip())
    if len(alt) >= 3:
        return alt[:3]
    if len(alt) > 0:
        return alt[:3]
    return []


def generate_three_captions(
    description: str,
    style: str,
    length: str,
    min_chars: int,
    max_chars: int,
    provider: Optional[str] = None,
    *,
    use_emoji: bool = True,
    use_punctuation: bool = True,
    elements: Optional[list[str]] = None,
    diversify: bool = False,
    supplement: Optional[str] = None,
    output_language: str = "zh-Hans",
    avoid_lexicon: Optional[Sequence[str]] = None,
    emoji_tone_appendix: Optional[str] = None,
    temperature: float = 0.82,
    verbose: bool = False,
    memory_context: Optional[str] = None,
) -> Optional[str]:
    """
    一次 API 调用生成三条候选的原始文本；解析请用 parse_three_candidates。
    失败返回 None。
    """
    if not description:
        return None
    backend, err = _resolve_backend(provider)
    if not backend:
        if verbose:
            print(f"错误：{err}")
        return None

    prompt = build_triple_caption_user_prompt(
        description,
        style,
        length,
        min_chars,
        max_chars,
        elements,
        use_emoji=use_emoji,
        use_punctuation=use_punctuation,
        diversify=diversify,
        supplement=supplement,
        output_language=output_language,
        avoid_lexicon=list(avoid_lexicon) if avoid_lexicon else None,
        emoji_tone_appendix=emoji_tone_appendix,
        memory_context=memory_context,
    )
    # 三条略长，单独给更大 max_tokens 上限但仍有封顶
    triple_cap = min(CAPTION_MAX_TOKENS * 2, 2000)
    return post_chat_completion(
        backend.url,
        backend.api_key,
        backend.model,
        prompt,
        temperature,
        max_tokens=triple_cap,
        verbose=verbose,
    )
