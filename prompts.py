"""朋友圈文案相关的提示词模板。"""
from __future__ import annotations

from typing import Optional

# Web/CLI 使用的语言代码 → 写入提示的说明（行首「候选n：」保持便于解析）
OUTPUT_LANGUAGE_LABELS: dict[str, str] = {
    "zh-Hans": "简体中文",
    "zh-Hant": "繁体中文",
    "en": "英文",
    "fr": "法语",
    "ja": "日文",
    "ko": "韩文",
    "mix": "中英自然混用",
}

# 网页风格下拉 value（英文/拼音）→ 写入提示的自然语言描述
STYLE_SLUG_TO_DESCRIPTION: dict[str, str] = {
    "humor": "幽默风趣，轻松好笑，自带梗但不油腻",
    "literary": "文艺清新，意象细腻，语气干净，像一句随笔",
    "concise": "简洁干练，短句利落，信息清楚，少废话",
    "lyrical": "歌词感：留白、节奏与意象并重，可略带押韵但不强行押韵",
    "daily_life": "生活随记：日常小事的温度感，像随手记下的生活片段",
    "travel": "旅行手记：出游/在路上的松弛感和新鲜感，带一点探索的喜悦",
    "fun": "玩梗整活：网络热梗、夸张自嘲，年轻化表达，不尬不油",
    "recommend": "种草安利：「这个真的绝了」的推荐语气，适合分享好物、好店、好去处",
}


def resolve_style_for_prompt(style: str | None) -> str:
    """将前端 slug 或旧版长文案映射为写入模型的风格描述；未知值原样返回。"""
    s = (style or "").strip()
    if s in STYLE_SLUG_TO_DESCRIPTION:
        return STYLE_SLUG_TO_DESCRIPTION[s]
    return s or "简洁自然"


OUTPUT_LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "zh-Hans": "除下行规定的行首标记外，三条正文的正文内容全部使用简体中文。",
    "zh-Hant": "除行首标记外，三条正文的正文内容全部使用繁体中文（台湾或香港常用字形均可）。",
    "en": "除行首标记外，三条正文的正文内容全部使用自然、地道的英文，像母语者发社交动态。",
    "fr": "除行首标记外，三条正文的正文内容全部使用自然、地道的法语。",
    "ja": "除行首标记外，三条正文的正文内容全部使用自然、地道的日文（可适当使用常见网络用语，勿过度）。",
    "ko": "除行首标记外，三条正文的正文内容全部使用自然、地道的韩文。",
    "mix": (
        "除行首标记外，三条正文的正文内容须符合：以简体中文为主要语言，但允许像小红书或微博博主那样，"
        "自然地穿插英文单词、短句或品牌名（例如：今天的 vibe 很 chill，谁懂？）；不要整段翻译，要自然混用；"
        "不要整段只用英文。"
    ),
}


def normalize_output_language(code: str | None) -> str:
    raw = (code or "zh-Hans").strip()
    aliases = {
        "zh": "zh-Hans",
        "cn": "zh-Hans",
        "简体": "zh-Hans",
        "简中": "zh-Hans",
        "tw": "zh-Hant",
        "hk": "zh-Hant",
        "繁体": "zh-Hant",
        "繁中": "zh-Hant",
        "zh-tw": "zh-Hant",
        "zh-hk": "zh-Hant",
        "english": "en",
        "法文": "fr",
        "法语": "fr",
        "日文": "ja",
        "日语": "ja",
        "韩文": "ko",
        "韩语": "ko",
    }
    aliases["mix"] = "mix"
    aliases["chinglish"] = "mix"
    aliases["中英夹杂"] = "mix"
    aliases["中英混用"] = "mix"
    key = aliases.get(raw.lower(), raw)
    if key not in OUTPUT_LANGUAGE_INSTRUCTIONS:
        return "zh-Hans"
    return key


def _supplement_block(supplement: str | None) -> str:
    s = (supplement or "").strip()
    if not s:
        return ""
    return f"""

【用户补充要求】（请尽量满足；若与安全、平台规范或上文硬性要求冲突，以合规与安全为先）
{s}
"""


def _avoid_lexicon_block(words: list[str] | None) -> str:
    """用户「避雷词」：与敏感词脱敏并行，在提示中做硬性用词约束。"""
    if not words:
        return ""
    # 控制长度，避免 prompt 膨胀
    shown = "、".join(words[:40])
    more = f" 等共 {len(words)} 项" if len(words) > 40 else ""
    return f"""

【硬性避雷】生成的文案中不得包含以下任何词语或同质化表达（含常见变体、谐音或缩写）：{shown}{more}。若不可避免触及语义近似，请换一种说法或改换意象。"""


def _memory_context_block(memory_context: str | None) -> str:
    """将偏好记忆摘要注入提示词（软参考口吻，不覆盖用户本次选择）。"""
    if not memory_context:
        return ""
    return f"""

{memory_context}"""


def _emoji_tone_block(appendix: str | None) -> str:
    if not (appendix or "").strip():
        return ""
    return f"""

{appendix.strip()}"""


def _language_block_single(output_language: str) -> str:
    lang = normalize_output_language(output_language)
    label = OUTPUT_LANGUAGE_LABELS.get(lang, "简体中文")
    inst = OUTPUT_LANGUAGE_INSTRUCTIONS.get(lang, OUTPUT_LANGUAGE_INSTRUCTIONS["zh-Hans"])
    return f"""

【输出语言】{label}（{inst}）"""


def _language_block_triple(output_language: str) -> str:
    lang = normalize_output_language(output_language)
    label = OUTPUT_LANGUAGE_LABELS.get(lang, "简体中文")
    inst = OUTPUT_LANGUAGE_INSTRUCTIONS.get(lang, OUTPUT_LANGUAGE_INSTRUCTIONS["zh-Hans"])
    return f"""

【输出语言】{label}（{inst}）
【重要】为便于程序解析，三条必须仍使用以下行首标记（「候选」「数字」「全角或半角冒号」须完全一致），标记本身用简体中文；冒号后的正文才是最终发文内容，须严格遵循上文【输出语言】中的全部要求。"""


def build_moments_caption_user_prompt(
    description: str,
    style: str = "简约干净",
    length: str = "约50字",
    elements: Optional[list[str]] = None,
    *,
    use_emoji: bool = True,
    use_punctuation: bool = True,
    supplement: Optional[str] = None,
    output_language: str = "zh-Hans",
    avoid_lexicon: Optional[list[str]] = None,
) -> str:
    """根据图片描述与偏好拼出发给文案模型的用户消息。"""
    style_resolved = resolve_style_for_prompt(style)
    elements_str = (
        f"，记得要巧妙融入这些元素：{', '.join(elements)}" if elements else ""
    )
    if use_emoji:
        emoji_rule = "可以适当使用 emoji 表情，但不要堆砌。"
    else:
        emoji_rule = "不要使用任何 emoji、颜文字或类似符号。"

    if use_punctuation:
        punct_rule = (
            "【强制标点规范】必须使用规范的全角中文标点（，。！？）；禁止使用空格代替标点符号进行断句。"
            "若输出英文则必须使用规范的半角标点。"
        )
    else:
        punct_rule = (
            "尽量不要使用标点符号；中文句间可用空格分隔，英文等可用空格分隔短语。"
        )

    return f"""你是一位精通社交媒体的文案高手。请根据以下图片描述，创作一条适合发朋友圈的文案。

图片描述：{description}
文案风格：{style_resolved}
字数要求：{length}{elements_str}

格式要求：
- {emoji_rule}
- {punct_rule}
{_language_block_single(output_language)}{_supplement_block(supplement)}{_avoid_lexicon_block(avoid_lexicon)}

请直接输出文案正文，不要带任何前缀或说明；须符合上文【输出语言】中的要求。"""


def build_triple_caption_user_prompt(
    description: str,
    style: str,
    length: str,
    min_chars: int,
    max_chars: int,
    elements: Optional[list[str]] = None,
    *,
    use_emoji: bool = True,
    use_punctuation: bool = True,
    diversify: bool = False,
    supplement: Optional[str] = None,
    output_language: str = "zh-Hans",
    avoid_lexicon: Optional[list[str]] = None,
    emoji_tone_appendix: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> str:
    """
    一次请求生成三条候选；要求固定格式便于解析。
    diversify=True 时提示模型换角度（用于「再生成」）。
    """
    style_resolved = resolve_style_for_prompt(style)
    elements_str = (
        f"，记得要巧妙融入这些元素：{', '.join(elements)}" if elements else ""
    )
    if use_emoji:
        emoji_rule = "可以适当使用 emoji，根据图片内容选择合适的表情。"
    else:
        emoji_rule = "不要使用任何 emoji、颜文字或类似符号。"

    if use_punctuation:
        punct_rule = (
            "【强制标点规范】中文正文必须使用规范的全角中文标点（，。！？）；禁止使用空格代替标点符号进行断句。"
            "若某条以英文或其他语言为主，则须使用该语言对应的规范标点（英文为半角）。"
        )
    else:
        punct_rule = "尽量不要使用标点符号；各语言均可用空格分隔意群。"

    hard = (
        f"【字数硬要求】三条每条在「候选n：」冒号之后的正文长度必须同时在 {min_chars}～{max_chars} 个字符之间"
        f"（按 Python len() 计数，含空格与 emoji）。超出或不足都视为不合格，请你在输出前自行删改至合规。"
    )
    div = (
        "\n请避免与常见套话雷同，三条切入角度要有明显差异（修辞、情绪、叙事重点至少一方面不同）。"
        if diversify
        else ""
    )

    return f"""你是一位精通社交媒体的文案高手。请根据以下图片描述，创作 **3 条** 不同的、适合发朋友圈的短文案。

图片描述：{description}
文案风格：{style_resolved}
字数软参考：{length}{elements_str}
{hard}
{_memory_context_block(memory_context)}
格式要求：
- {emoji_rule}
- {punct_rule}
{_language_block_triple(output_language)}{_supplement_block(supplement)}{_avoid_lexicon_block(avoid_lexicon)}
{div}

【输出格式（必须严格遵守）】
每条单独一行，且行首必须完全匹配以下标记（共三行，不要加空行或序号其它形式）：
候选1：正文内容
候选2：正文内容
候选3：正文内容

「候选1：」到行尾之间即为该条正文（须为目标输出语言）；不要另加引号或书名号包裹整句。{_emoji_tone_block(emoji_tone_appendix)}"""
