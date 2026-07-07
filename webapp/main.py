"""朋友圈文案 Web：上传多图、三候选、再生成（仅文案）、敏感词与字数校验。"""
from __future__ import annotations

import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from config import AGENT_REVIEW_ENABLED, AGENT_REVIEW_MAX_RETRIES
from llm.caption import generate_three_captions, parse_three_candidates
from media_validate import sniff_image_mime
from prompts import OUTPUT_LANGUAGE_INSTRUCTIONS, normalize_output_language
from safety import find_hits, mask_sensitive, merge_blocked_words
from image_color_utils import build_emoji_tone_prompt_appendix, extract_dominant_colors_and_warmth
from vision_tools import get_image_description
from agent_review import parse_review_result, review_candidates
from agent_memory import build_memory_context, get_memory_display_hint, record_feedback

STATIC_DIR = Path(__file__).resolve().parent / "static"

SUPPLEMENT_MAX_LEN = 4000
INSPIRATION_MAX = 1200
TEXT_IDEA_MAX = 2000
EMOJI_APPENDIX_STORE_MAX = 800

app = FastAPI(title="配图说", version="1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── 异步审稿存储（后台线程写入，前端轮询读取）──────────────────────────────
_review_store: dict[str, dict[str, Any]] = {}
_review_store_lock = threading.Lock()


def _bg_review(
    review_id: str,
    *,
    candidates: list[str],
    description: str,
    min_chars: int,
    max_chars: int,
    avoid_lexicon: list[str],
    output_language: str,
    style: str,
    provider: str,
    memory_context: str | None,
    blocked: list[str],
) -> None:
    """后台线程：跑评审 + 不达标重试，结果写入 _review_store。"""
    try:
        result = _run_agent_review_if_enabled(
            candidates=candidates,
            description=description,
            min_chars=min_chars,
            max_chars=max_chars,
            avoid_lexicon=avoid_lexicon,
            output_language=output_language,
            style=style,
            provider=provider,
            memory_context=memory_context,
            verbose=True,
        )
    except Exception as exc:
        with _review_store_lock:
            _review_store[review_id] = {
                "status": "error",
                "error": f"审稿异常：{exc}",
                "ts": time.time(),
            }
        return

    # 如果触发了重试，对重试候选做敏感词处理
    if result.get("triggered_retry") and result.get("retry_candidates"):
        masked_retry: list[dict[str, Any]] = []
        for i, text in enumerate(result["retry_candidates"][:3]):
            hits = find_hits(text, blocked)
            masked = mask_sensitive(text, blocked)
            ln = len(masked)
            masked_retry.append({
                "index": i + 1,
                "text": masked,
                "length": ln,
                "length_ok": min_chars <= ln <= max_chars,
                "sensitive_hits": hits,
                "sensitive_masked": bool(hits),
            })
        result["retry_candidates"] = masked_retry

    # 清理内部字段并确保 enabled 标记存在
    result.pop("triggered_retry", None)
    result["enabled"] = True

    with _review_store_lock:
        _review_store[review_id] = {"status": "done", "result": result, "ts": time.time()}


def _bool_form(v: str) -> bool:
    return str(v).lower() in ("1", "true", "yes", "on")


def length_hint_from_bounds(min_chars: int, max_chars: int) -> str:
    """由字数上下限生成传给提示词的「软」长度说明（硬校验仍由 min/max 控制）。"""
    return f"字数必须在 {min_chars} 到 {max_chars} 个字符之间（与下文硬性字数区间一致）。"


def _extra_blocked_from_form(raw: str | None) -> list[str]:
    """每行一词，或一行内用中英文逗号、顿号、分号分隔。"""
    if not raw:
        return []
    out: list[str] = []
    for ln in raw.splitlines():
        t = ln.strip()
        if not t or t.startswith("#"):
            continue
        for part in re.split(r"[,，、;；]+", t):
            w = part.strip()
            if w:
                out.append(w)
    return out


def _clean_supplement(s: str | None) -> str | None:
    t = (s or "").strip()
    if not t:
        return None
    return t[:SUPPLEMENT_MAX_LEN]


def merge_supplement_with_inspiration(
    supplement: str | None,
    inspiration: str | None,
) -> str | None:
    """将自由补充与「引用灵感」合并为一条发给模型的补充说明。"""
    parts: list[str] = []
    base = (supplement or "").strip()
    if base:
        parts.append(base)
    ins = (inspiration or "").strip()[:INSPIRATION_MAX]
    if ins:
        parts.append(
            "【引用灵感】（仅作语气、意象或句式参考，请自然融入短句，勿整段照搬）\n" + ins
        )
    if not parts:
        return None
    return _clean_supplement("\n\n".join(parts))


def _run_agent_review_if_enabled(
    *,
    candidates: list[str],
    description: str,
    min_chars: int,
    max_chars: int,
    avoid_lexicon: list[str],
    output_language: str,
    style: str,
    provider: str,
    memory_context: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """对已生成的三条候选执行自评审；不达标时自动重试一次。

    返回的 dict 始终包含 review 信息；若触发了重试，还包含
    triggered_retry / retry_candidates / retry_review 三个内部字段，
    由调用方 _build_candidates_payload 处理替换。
    """
    base: dict[str, Any] = {"enabled": AGENT_REVIEW_ENABLED}

    if not AGENT_REVIEW_ENABLED:
        return base

    if len(candidates) < 3:
        base["skipped"] = True
        base["skip_reason"] = "候选不足3条，跳过评审"
        return base

    # ── 第一轮评审 ──
    review_raw = review_candidates(
        candidates,
        min_chars=min_chars,
        max_chars=max_chars,
        avoid_lexicon=avoid_lexicon,
        output_language=output_language,
        style=style,
        provider=provider,
        verbose=verbose,
    )
    first_review = parse_review_result(review_raw, verbose=verbose) if review_raw else None

    if first_review is None:
        base["parse_error"] = True
        base["error"] = "评审结果解析失败（模型可能未按要求返回JSON），已降级使用原始候选"
        return base

    first_dict = first_review.to_dict()
    first_dict["round"] = 1

    if first_review.meets_threshold or AGENT_REVIEW_MAX_RETRIES < 1:
        # 达标或不允许重试 → 直接返回
        first_dict["retried"] = False
        return first_dict

    # ── 不达标 → 重试一次 ──
    if verbose:
        print(
            f"[Agent Review] 首轮及格 {first_review.pass_count}/3，"
            f"未达阈值 {first_review.pass_count}/{AGENT_REVIEW_MAX_RETRIES}，触发重试…"
        )

    # 重试生成（diversify + 更高温度 + 追加避雷提醒到 supplement）
    retry_raw = generate_three_captions(
        description,
        style,
        f"字数必须在 {min_chars} 到 {max_chars} 个字符之间",
        min_chars,
        max_chars,
        provider=provider,
        use_emoji=True,
        use_punctuation=True,
        diversify=True,
        supplement=(
            f"上一次生成的文案未通过审核，请特别注意：避开以下词语（{', '.join(avoid_lexicon[:10])}），"
            f"确保每条字数在 {min_chars}-{max_chars} 之间，三条之间角度要有明显差异。"
        ),
        output_language=output_language,
        avoid_lexicon=avoid_lexicon,
        emoji_tone_appendix=None,
        temperature=0.95,
        verbose=False,
        memory_context=memory_context,
    )

    if not retry_raw:
        first_dict["retried"] = False
        first_dict["retry_failed"] = True
        first_dict["retry_reason"] = "重试生成调用失败"
        return first_dict

    retry_cands = parse_three_candidates(retry_raw)
    if len(retry_cands) < 3:
        first_dict["retried"] = False
        first_dict["retry_failed"] = True
        first_dict["retry_reason"] = f"重试解析仅得到 {len(retry_cands)} 条"
        return first_dict

    # ── 第二轮评审 ──
    review_raw2 = review_candidates(
        retry_cands,
        min_chars=min_chars,
        max_chars=max_chars,
        avoid_lexicon=avoid_lexicon,
        output_language=output_language,
        style=style,
        provider=provider,
        verbose=verbose,
    )
    second_review = parse_review_result(review_raw2, verbose=verbose) if review_raw2 else None

    first_dict["retried"] = True

    if second_review is None:
        # 二轮评审解析失败，但仍返回新的候选（附带首轮评审信息）
        return {
            **first_dict,
            "triggered_retry": True,
            "retry_candidates": retry_cands,
            "retry_review": {
                "enabled": True,
                "round": 2,
                "parse_error": True,
                "error": "重试后评审解析失败",
                "retried": True,
            },
        }

    second_dict = second_review.to_dict()
    second_dict["round"] = 2
    second_dict["retried"] = True

    if second_review.pass_count >= first_review.pass_count:
        # 重试有改善 → 使用重试结果
        return {
            **second_dict,
            "triggered_retry": True,
            "retry_candidates": retry_cands,
            "retry_review": second_dict,
        }

    # 重试没有改善 → 保留原结果
    first_dict["retry_no_improvement"] = True
    first_dict["retry_pass_count"] = second_review.pass_count
    return first_dict


def _build_candidates_payload(
    raw: str | None,
    *,
    min_chars: int,
    max_chars: int,
    blocked: list[str],
    diversify_retry: bool,
    description: str | None,
    style: str,
    length_hint: str,
    use_emoji: bool,
    use_punctuation: bool,
    provider: str,
    supplement: str | None,
    output_language: str,
    avoid_lexicon: list[str],
    emoji_tone_appendix: str | None,
    memory_context: str | None = None,
    async_review_id: str | None = None,
) -> dict[str, Any]:
    if not raw:
        return {"ok": False, "error": "文案模型未返回内容，请稍后重试或更换模型。"}
    cands = parse_three_candidates(raw)
    if len(cands) < 3 and diversify_retry:
        raw2 = generate_three_captions(
            description or "",
            style,
            length_hint,
            min_chars,
            max_chars,
            provider=provider,
            use_emoji=use_emoji,
            use_punctuation=use_punctuation,
            diversify=True,
            supplement=supplement,
            output_language=output_language,
            avoid_lexicon=avoid_lexicon,
            emoji_tone_appendix=emoji_tone_appendix,
            temperature=0.92,
            verbose=False,
            memory_context=memory_context,
        )
        if raw2:
            cands2 = parse_three_candidates(raw2)
            if len(cands2) >= len(cands):
                cands = cands2

    items: list[dict[str, Any]] = []
    cand_texts: list[str] = []
    for i, text in enumerate(cands[:3]):
        hits = find_hits(text, blocked)
        masked = mask_sensitive(text, blocked)
        ln = len(masked)
        items.append(
            {
                "index": i + 1,
                "text": masked,
                "length": ln,
                "length_ok": min_chars <= ln <= max_chars,
                "sensitive_hits": hits,
                "sensitive_masked": bool(hits),
            }
        )
        cand_texts.append(masked)

    payload: dict[str, Any] = {"ok": True, "candidates": items}

    # ── Agent 自评审 ──────────────────────────────────────────────────────
    if async_review_id:
        # 异步模式：后台线程跑审稿，不阻塞响应
        threading.Thread(
            target=_bg_review,
            args=(async_review_id,),
            kwargs=dict(
                candidates=cand_texts,
                description=description or "",
                min_chars=min_chars,
                max_chars=max_chars,
                avoid_lexicon=avoid_lexicon,
                output_language=output_language,
                style=style,
                provider=provider,
                memory_context=memory_context,
                blocked=blocked,
            ),
            daemon=True,
        ).start()
        payload["review_id"] = async_review_id
    else:
        # 同步模式（CLI 等场景）
        review_info: dict[str, Any] = _run_agent_review_if_enabled(
            candidates=cand_texts,
            description=description or "",
            min_chars=min_chars,
            max_chars=max_chars,
            avoid_lexicon=avoid_lexicon,
            output_language=output_language,
            style=style,
            provider=provider,
            memory_context=memory_context,
            verbose=True,
        )
        if (
            review_info.get("triggered_retry")
            and review_info.get("retry_candidates")
            and review_info.get("retry_review")
        ):
            retry_cands: list[str] = review_info["retry_candidates"]
            retry_review: dict = review_info["retry_review"]
            new_items: list[dict[str, Any]] = []
            for i, text in enumerate(retry_cands[:3]):
                hits = find_hits(text, blocked)
                masked = mask_sensitive(text, blocked)
                ln = len(masked)
                new_items.append(
                    {
                        "index": i + 1,
                        "text": masked,
                        "length": ln,
                        "length_ok": min_chars <= ln <= max_chars,
                        "sensitive_hits": hits,
                        "sensitive_masked": bool(hits),
                    }
                )
            items = new_items
            review_info = retry_review
            payload["candidates"] = items

        review_info.pop("triggered_retry", None)
        review_info.pop("retry_candidates", None)
        review_info.pop("retry_review", None)

        if review_info:
            review_info["enabled"] = True
            payload["review"] = review_info

    return payload


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/full")
async def api_full(
    files: list[UploadFile] = File(default=[]),
    style: Annotated[str, Form()] = "humor",
    use_emoji: Annotated[str, Form()] = "true",
    use_punctuation: Annotated[str, Form()] = "true",
    provider: Annotated[str, Form()] = "deepseek",
    min_chars: Annotated[int, Form()] = 10,
    max_chars: Annotated[int, Form()] = 72,
    extra_blocked: Annotated[str | None, Form()] = None,
    supplement: Annotated[str | None, Form()] = None,
    inspiration: Annotated[str | None, Form()] = None,
    output_language: Annotated[str, Form()] = "zh-Hans",
    no_image_mode: Annotated[str, Form()] = "false",
    text_idea: Annotated[str | None, Form()] = None,
    emoji_color_suggest: Annotated[str, Form()] = "false",
) -> JSONResponse:
    """上传 0～9 张图（或无图模式）：看图或读用户想法，再生成三条候选文案。"""
    if min_chars > max_chars:
        raise HTTPException(400, "最小字数不能大于最大字数")
    if len(files) > 9:
        raise HTTPException(400, "最多 9 张图片")

    length_hint = length_hint_from_bounds(min_chars, max_chars)
    extra_list = _extra_blocked_from_form(extra_blocked)
    blocked = merge_blocked_words(extra_list)
    ue = _bool_form(use_emoji)
    up = _bool_form(use_punctuation)
    sup = merge_supplement_with_inspiration(supplement, inspiration)
    olang = normalize_output_language(output_language)
    if olang not in OUTPUT_LANGUAGE_INSTRUCTIONS:
        olang = "zh-Hans"

    no_im = _bool_form(no_image_mode)
    idea = (text_idea or "").strip()[:TEXT_IDEA_MAX]
    want_emoji_tone = _bool_form(emoji_color_suggest)

    if no_im and idea:
        if files:
            raise HTTPException(400, "无图片模式下请勿同时上传图片；请取消勾选或清空文字想法。")
        desc = idea
        emoji_appendix: str | None = None
        mem_ctx = build_memory_context()
        raw = generate_three_captions(
            desc,
            style,
            length_hint,
            min_chars,
            max_chars,
            provider=provider.strip() or None,
            use_emoji=ue,
            use_punctuation=up,
            diversify=False,
            supplement=sup,
            output_language=olang,
            avoid_lexicon=extra_list,
            emoji_tone_appendix=emoji_appendix,
            temperature=0.82,
            verbose=False,
            memory_context=mem_ctx,
        )
        payload = _build_candidates_payload(
            raw,
            min_chars=min_chars,
            max_chars=max_chars,
            blocked=blocked,
            diversify_retry=True,
            description=desc,
            style=style,
            length_hint=length_hint,
            use_emoji=ue,
            use_punctuation=up,
            provider=provider.strip() or "deepseek",
            supplement=sup,
            output_language=olang,
            avoid_lexicon=extra_list,
            emoji_tone_appendix=emoji_appendix,
            memory_context=mem_ctx,
            async_review_id=str(uuid.uuid4())[:8],
        )
        payload["description"] = desc
        payload["output_language"] = olang
        payload["emoji_tone_appendix"] = ""
        mem_hint = get_memory_display_hint()
        if mem_hint:
            payload["memory"] = mem_hint
        if not payload.get("ok"):
            return JSONResponse(payload, status_code=502)
        return JSONResponse(payload)

    if not files:
        raise HTTPException(400, "请上传至少一张图片，或勾选「无图片」并填写想法。")
    with tempfile.TemporaryDirectory(prefix="moments_") as tmp:
        paths: list[str] = []
        for i, uf in enumerate(files[:9]):
            data = await uf.read()
            mime, err = sniff_image_mime(data)
            if err or not mime:
                raise HTTPException(400, f"{uf.filename or i}: {err or '无效文件'}")
            suf = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp",
            }.get(mime, ".img")
            p = Path(tmp) / f"{i}{suf}"
            p.write_bytes(data)
            paths.append(str(p))

        emoji_appendix = None
        color_data = None
        # 颜色分析始终做（只要有图），用于前端展示；复选框只控制是否写入 prompt
        if paths:
            try:
                colors, warmth = extract_dominant_colors_and_warmth(paths[0])
                color_data = {
                    "colors": [{"r": c[0], "g": c[1], "b": c[2]} for c in colors],
                    "warmth": warmth,
                }
                if want_emoji_tone:
                    emoji_appendix = build_emoji_tone_prompt_appendix(warmth)
            except Exception:
                color_data = None
                emoji_appendix = None

        desc = get_image_description(paths, verbose=False)
        if not desc:
            return JSONResponse(
                {"ok": False, "error": "图片理解失败，请检查 QWEN_API_KEY 与图片内容。"},
                status_code=502,
            )

        mem_ctx = build_memory_context()
        raw = generate_three_captions(
            desc,
            style,
            length_hint,
            min_chars,
            max_chars,
            provider=provider.strip() or None,
            use_emoji=ue,
            use_punctuation=up,
            diversify=False,
            supplement=sup,
            output_language=olang,
            avoid_lexicon=extra_list,
            emoji_tone_appendix=emoji_appendix,
            temperature=0.82,
            verbose=False,
            memory_context=mem_ctx,
        )
        payload = _build_candidates_payload(
            raw,
            min_chars=min_chars,
            max_chars=max_chars,
            blocked=blocked,
            diversify_retry=True,
            description=desc,
            style=style,
            length_hint=length_hint,
            use_emoji=ue,
            use_punctuation=up,
            provider=provider.strip() or "deepseek",
            supplement=sup,
            output_language=olang,
            avoid_lexicon=extra_list,
            emoji_tone_appendix=emoji_appendix,
            memory_context=mem_ctx,
            async_review_id=str(uuid.uuid4())[:8],
        )
        payload["description"] = desc
        payload["output_language"] = olang
        payload["emoji_tone_appendix"] = (
            (emoji_appendix or "")[:EMOJI_APPENDIX_STORE_MAX] if emoji_appendix else ""
        )
        if color_data:
            payload["color_analysis"] = color_data
        mem_hint = get_memory_display_hint()
        if mem_hint:
            payload["memory"] = mem_hint
        if not payload.get("ok"):
            return JSONResponse(payload, status_code=502)
        return JSONResponse(payload)


class RegenerateBody(BaseModel):
    description: str = Field(..., min_length=1, max_length=12000)
    style: str = "humor"
    use_emoji: bool = True
    use_punctuation: bool = True
    provider: str = "deepseek"
    min_chars: int = Field(10, ge=1, le=500)
    max_chars: int = Field(72, ge=1, le=500)
    extra_blocked_lines: str = ""
    supplement: str = Field(default="", max_length=SUPPLEMENT_MAX_LEN)
    inspiration: str = Field(default="", max_length=INSPIRATION_MAX)
    output_language: str = "zh-Hans"
    emoji_tone_appendix: str = Field(default="", max_length=EMOJI_APPENDIX_STORE_MAX)

    @model_validator(mode="after")
    def _bounds(self) -> RegenerateBody:
        if self.min_chars > self.max_chars:
            raise ValueError("min_chars 不能大于 max_chars")
        return self


@app.post("/api/regenerate")
def api_regenerate(body: RegenerateBody) -> JSONResponse:
    """在已有画面描述上，仅更新三条候选文案。"""
    length_hint = length_hint_from_bounds(body.min_chars, body.max_chars)
    extra = _extra_blocked_from_form(body.extra_blocked_lines or None)
    blocked = merge_blocked_words(extra)
    sup = merge_supplement_with_inspiration(
        body.supplement or None,
        body.inspiration or None,
    )
    olang = normalize_output_language(body.output_language)
    if olang not in OUTPUT_LANGUAGE_INSTRUCTIONS:
        olang = "zh-Hans"

    emoji_apx = (body.emoji_tone_appendix or "").strip() or None

    mem_ctx = build_memory_context()
    raw = generate_three_captions(
        body.description.strip(),
        body.style,
        length_hint,
        body.min_chars,
        body.max_chars,
        provider=body.provider.strip() or None,
        use_emoji=body.use_emoji,
        use_punctuation=body.use_punctuation,
        diversify=True,
        supplement=sup,
        output_language=olang,
        avoid_lexicon=extra,
        emoji_tone_appendix=emoji_apx,
        temperature=0.9,
        verbose=False,
        memory_context=mem_ctx,
    )
    payload = _build_candidates_payload(
        raw,
        min_chars=body.min_chars,
        max_chars=body.max_chars,
        blocked=blocked,
        diversify_retry=True,
        description=body.description,
        style=body.style,
        length_hint=length_hint,
        use_emoji=body.use_emoji,
        use_punctuation=body.use_punctuation,
        provider=body.provider.strip() or "deepseek",
        supplement=sup,
        output_language=olang,
        avoid_lexicon=extra,
        emoji_tone_appendix=emoji_apx,
        memory_context=mem_ctx,
        async_review_id=str(uuid.uuid4())[:8],
    )
    payload["output_language"] = olang
    mem_hint = get_memory_display_hint()
    if mem_hint:
        payload["memory"] = mem_hint
    if not payload.get("ok"):
        return JSONResponse(payload, status_code=502)
    return JSONResponse(payload)


@app.get("/api/review/{review_id}")
def api_review_poll(review_id: str) -> JSONResponse:
    """前端轮询审稿结果。返回 {"status":"pending"} 或 {"status":"done","review":{...}}。"""
    with _review_store_lock:
        entry = _review_store.get(review_id)
    if entry is None:
        return JSONResponse({"status": "pending"})
    if entry.get("status") == "done":
        # 读取后立即清理，避免内存堆积
        with _review_store_lock:
            _review_store.pop(review_id, None)
        return JSONResponse({"status": "done", "review": entry["result"]})
    if entry.get("status") == "error":
        with _review_store_lock:
            _review_store.pop(review_id, None)
        return JSONResponse({"status": "error", "error": entry.get("error", "未知错误")})
    return JSONResponse({"status": "pending"})


class FeedbackBody(BaseModel):
    style: str = ""
    adopted: bool = False


@app.post("/api/feedback")
def api_feedback(body: FeedbackBody) -> JSONResponse:
    """记录用户对本次生成结果的反馈：复制某条 = 采纳，点换三条 = 未采纳。"""
    record_feedback(body.style, body.adopted)
    mem_hint = get_memory_display_hint()
    return JSONResponse({"ok": True, "memory": mem_hint})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
