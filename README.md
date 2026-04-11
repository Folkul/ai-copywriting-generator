# 配图配文

1～9 张本地图经 **通义千问 VL** 理解画面，再用 **DeepSeek** 或 **通义千问文本** 生成短配文。支持 **emoji / 标点**、**补充想法**、**歌词感与歌词摘录**、**多语言输出**（简中 / 繁中 / 英 / 法 / 日 / 韩）。提供 **命令行** 与 **网页**。

## 环境

- Python 3.10+
- `pip install -r requirements.txt`

## 配置

复制 `.env.example` 为 `.env`，配置 `QWEN_API_KEY`；使用 DeepSeek 写文案时配置 `DEEPSEEK_API_KEY`。默认文案模型：`CAPTION_PROVIDER=deepseek` 或 `qwen`。

可选环境与稳定性相关变量：

- `CAPTION_MAX_TOKENS`：单次文案 API 最大输出 token（默认 700；一次生成三条时会自动放宽上限）
- `LLM_REQUEST_TIMEOUT`：超时秒数
- `blocked_words.txt`：项目根目录敏感词表（一行一词，`#` 开头为注释），可从 `blocked_words.example.txt` 复制改名；已加入 `.gitignore`

## 网页（推荐）

在项目根目录执行：

```bash
uvicorn webapp.main:app --host 127.0.0.1 --port 8765
```

浏览器打开 `http://127.0.0.1:8765`：

- 拖拽或选择多图、**选择文件夹**（自动筛图片，最多 9 张）
- 选风格、字数说明、**最少/最多字数硬校验**、emoji/标点开关、文案模型、**输出语言**、**补充要求**（想法/示例/避雷等）
- **生成三条**：看图一次后，一次给出三种说法（同一回复内解析）
- **换三条说法**：在已有画面描述上刷新文案，无需重新上传图片
- 选项写入 **localStorage**（含补充、歌词感、输出语言等）；画面描述在 **sessionStorage**，刷新页面后「换三条」需先完整生成一次

敏感词：服务端 `blocked_words.txt` + 页面「额外敏感词」合并，命中则 **脱敏为星号**。

## 命令行

```bash
python main.py --list-providers
python main.py test.jpg
python main.py a.jpg b.jpg --style 文艺青年 --no-emoji
python main.py test.jpg --language en --supplement "Short, witty, no hashtags"
python test_vision.py
python test_vision.py 1.jpg 2.jpg --no-emoji
```

## 结构

- `config.py` — 环境变量
- `prompts.py` — 单条 / 三条候选提示词
- `vision_tools.py` — 多图 VL
- `llm/http_chat.py` — OpenAI 兼容 HTTP（`max_tokens` 封顶）
- `llm/caption.py` — 文案与解析
- `safety.py` — 敏感词合并与脱敏
- `media_validate.py` — 上传图片魔数校验
- `webapp/main.py` + `webapp/static/*` — Web UI
- `main.py` — CLI
