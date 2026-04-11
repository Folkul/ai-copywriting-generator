"""敏感词过滤：合并服务端词表与客户端提交的额外词。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from config import BLOCKED_WORDS_FILE, PROJECT_ROOT


def _read_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    words: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        words.append(s)
    return words


def _resolved_blocked_path() -> Path:
    p = BLOCKED_WORDS_FILE
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def load_server_blocked_words() -> list[str]:
    """从 BLOCKED_WORDS_FILE 指向的文件加载。"""
    return _read_lines(_resolved_blocked_path())


def merge_blocked_words(extra: Iterable[str] | None) -> list[str]:
    base = load_server_blocked_words()
    seen: set[str] = set()
    out: list[str] = []
    for w in list(base) + list(extra or []):
        t = w.strip()
        if not t or t.startswith("#") or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def find_hits(text: str, words: list[str]) -> list[str]:
    """返回在 text 中出现的敏感词（子串匹配）。"""
    if not text or not words:
        return []
    hits: list[str] = []
    for w in words:
        if w and w in text:
            hits.append(w)
    return hits


def mask_sensitive(text: str, words: list[str]) -> str:
    """将命中词替换为星号（每条词最多 8 个星）。"""
    out = text
    for w in find_hits(text, words):
        repl = "*" * min(len(w), 8)
        out = out.replace(w, repl)
    return out
