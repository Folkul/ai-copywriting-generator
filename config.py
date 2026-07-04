"""环境变量与默认模型配置。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# #region agent log
def _agent_debug_log(location: str, message: str, data: dict, hypothesis_id: str = "") -> None:
    try:
        import json
        import time

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

_env_dotenv_ok = load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# --- 密钥 ---
QWEN_API_KEY = _env("QWEN_API_KEY")
DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")

# #region agent log
_agent_debug_log(
    "config.py:after_keys",
    "dotenv and key lengths",
    {
        "dotenv_loaded_file": _env_dotenv_ok,
        "cwd": str(Path.cwd()),
        "qwen_key_len": len(QWEN_API_KEY),
        "deepseek_key_len": len(DEEPSEEK_API_KEY),
    },
    "H1-H2",
)
# #endregion

# --- 视觉（千问 VL）---
QWEN_VL_MODEL = _env("QWEN_VL_MODEL", "qwen-vl-plus")
MAX_IMAGES = 9

# --- 文案：默认后端与超时 ---
CAPTION_PROVIDER = _env("CAPTION_PROVIDER", "deepseek").lower()
LLM_REQUEST_TIMEOUT = int(_env("LLM_REQUEST_TIMEOUT", "120") or "120")
# 限制输出长度，利于省钱与稳定
CAPTION_MAX_TOKENS = int(_env("CAPTION_MAX_TOKENS", "700") or "700")

# DeepSeek
DEEPSEEK_CHAT_URL = _env("DEEPSEEK_CHAT_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_CHAT_MODEL = _env("DEEPSEEK_CHAT_MODEL", "deepseek-chat")

# 通义千问文本（DashScope 兼容模式，与 VL 共用 QWEN_API_KEY）
QWEN_COMPAT_CHAT_URL = _env(
    "QWEN_COMPAT_CHAT_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
)
QWEN_TEXT_MODEL = _env("QWEN_TEXT_MODEL", "qwen-turbo")

# 单张图片大小上限（字节）
MAX_IMAGE_BYTES = int(_env("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)) or str(10 * 1024 * 1024))

# --- Agent 自评审（可选）---
# 设为 "false" / "0" / "no" 可完全关闭评审，此时退化为原有固定流程
AGENT_REVIEW_ENABLED = _env("AGENT_REVIEW_ENABLED", "true").lower() in ("1", "true", "yes", "on")
# 三条中至少 N 条平均分 >= AGENT_REVIEW_SCORE_THRESHOLD 才算通过，否则触发重试
AGENT_REVIEW_PASS_THRESHOLD = int(_env("AGENT_REVIEW_PASS_THRESHOLD", "2") or "2")
# 单条平均分（safety/length/quality/diversity 四项均值）>= 此值算及格
AGENT_REVIEW_SCORE_THRESHOLD = int(_env("AGENT_REVIEW_SCORE_THRESHOLD", "6") or "6")
# 评审不通过时最多重试生成几次（0 = 不重试，推荐 1）
AGENT_REVIEW_MAX_RETRIES = int(_env("AGENT_REVIEW_MAX_RETRIES", "1") or "1")

# --- Agent 偏好记忆（可选）---
# 设为 "false" / "0" / "no" 可关闭偏好记忆
AGENT_MEMORY_ENABLED = _env("AGENT_MEMORY_ENABLED", "true").lower() in ("1", "true", "yes", "on")
# 历史文件保留的最大条数
AGENT_MEMORY_MAX_ENTRIES = int(_env("AGENT_MEMORY_MAX_ENTRIES", "10") or "10")
# 注入 prompt 时参考最近 N 条
AGENT_MEMORY_CONTEXT_ENTRIES = int(_env("AGENT_MEMORY_CONTEXT_ENTRIES", "5") or "5")

# 敏感词表（可选）：项目根目录 blocked_words.txt，一行一词
PROJECT_ROOT = Path(__file__).resolve().parent
_bw = _env("BLOCKED_WORDS_FILE")
BLOCKED_WORDS_FILE = Path(_bw) if _bw else (PROJECT_ROOT / "blocked_words.txt")
