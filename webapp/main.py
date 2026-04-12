"""朋友圈文案 Web：上传多图、三候选、再生成（仅文案）、敏感词与字数校验。"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from llm.caption import generate_three_captions, parse_three_candidates
from media_validate import sniff_image_mime
from prompts import OUTPUT_LANGUAGE_INSTRUCTIONS, normalize_output_language
from safety import find_hits, mask_sensitive, merge_blocked_words
from vision_tools import get_image_description

STATIC_DIR = Path(__file__).resolve().parent / "static"

SUPPLEMENT_MAX_LEN = 4000
INSPIRATION_MAX = 1200

app = FastAPI(title="配图说", version="1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


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
            temperature=0.92,
            verbose=False,
        )
        if raw2:
            cands2 = parse_three_candidates(raw2)
            if len(cands2) >= len(cands):
                cands = cands2

    items: list[dict[str, Any]] = []
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
    return {"ok": True, "candidates": items}


@app.get("/")
def index_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/full")
async def api_full(
    files: Annotated[list[UploadFile], File()],
    style: Annotated[str, Form()] = "简约干净",
    use_emoji: Annotated[str, Form()] = "true",
    use_punctuation: Annotated[str, Form()] = "true",
    provider: Annotated[str, Form()] = "deepseek",
    min_chars: Annotated[int, Form()] = 10,
    max_chars: Annotated[int, Form()] = 72,
    extra_blocked: Annotated[str | None, Form()] = None,
    supplement: Annotated[str | None, Form()] = None,
    inspiration: Annotated[str | None, Form()] = None,
    output_language: Annotated[str, Form()] = "zh-Hans",
) -> JSONResponse:
    """上传 1～9 张图：看图一次，再生成三条候选文案。"""
    if min_chars > max_chars:
        raise HTTPException(400, "最小字数不能大于最大字数")
    if not files:
        raise HTTPException(400, "请至少上传一张图片")
    if len(files) > 9:
        raise HTTPException(400, "最多 9 张图片")

    length_hint = length_hint_from_bounds(min_chars, max_chars)
    blocked = merge_blocked_words(_extra_blocked_from_form(extra_blocked))
    ue = _bool_form(use_emoji)
    up = _bool_form(use_punctuation)
    sup = merge_supplement_with_inspiration(supplement, inspiration)
    olang = normalize_output_language(output_language)
    if olang not in OUTPUT_LANGUAGE_INSTRUCTIONS:
        olang = "zh-Hans"

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

        desc = get_image_description(paths, verbose=False)
        if not desc:
            return JSONResponse(
                {"ok": False, "error": "图片理解失败，请检查 QWEN_API_KEY 与图片内容。"},
                status_code=502,
            )

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
            temperature=0.82,
            verbose=False,
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
        )
        payload["description"] = desc
        payload["output_language"] = olang
        if not payload.get("ok"):
            return JSONResponse(payload, status_code=502)
        return JSONResponse(payload)


class RegenerateBody(BaseModel):
    description: str = Field(..., min_length=1, max_length=12000)
    style: str = "简约干净"
    use_emoji: bool = True
    use_punctuation: bool = True
    provider: str = "deepseek"
    min_chars: int = Field(10, ge=1, le=500)
    max_chars: int = Field(72, ge=1, le=500)
    extra_blocked_lines: str = ""
    supplement: str = Field(default="", max_length=SUPPLEMENT_MAX_LEN)
    inspiration: str = Field(default="", max_length=INSPIRATION_MAX)
    output_language: str = "zh-Hans"

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
        temperature=0.9,
        verbose=False,
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
    )
    payload["output_language"] = olang
    if not payload.get("ok"):
        return JSONResponse(payload, status_code=502)
    return JSONResponse(payload)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
