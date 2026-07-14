# 配图说 —— AI 多模型 Agent 协作生成社交媒体文案

上传 1～9 张图片（或直接描述想法），AI 先理解画面内容，再按你选的风格一键生成三条候选文案。支持微信朋友圈、小红书、微博、商品种草、商业推广等场景。

> 拍照 3 分钟，配文 30 秒——给每张照片配上它该有的好文案。

---

## 为什么做这个

"图拍好了，文案想半天"是社交媒体时代的真实痛点。修图工具层出不穷，但**内容生成**这个环节几乎没有趁手工具——大多数人要么硬憋，要么发个表情敷衍。

配图说的目标用户不只是普通社交用户。**小微商家**需要为产品图写吸引人的种草文案，**内容创作者**需要在多个平台上维持稳定的内容输出。这些场景的共同需求是：看图 → 出文案 → 快速发布，整个过程不拖沓、不费力。

本项目试图用一个轻量但完整的 Agent 系统解决这个问题：不只是一次 API 调用，而是 **视觉理解 + 文案生成 + 质量审稿 + 偏好学习** 的多步骤协作流程。

---

## 核心亮点

| 亮点 | 说明 |
|---|---|
| **多模型 Agent 协作** | Qwen VL 看图理解 → DeepSeek/Qwen 生成文案 → Agent 审稿把关 → 偏好记忆持续优化，形成完整闭环 |
| **自评审 + 自动重试** | 后台调模型从避雷、字数、创意、差异性四维逐条打分，不达标自动以更高温度重试 |
| **偏好记忆** | 记录采纳/拒绝历史，以自然语言摘要注入 prompt 作为软参考——模型自主判断，而非硬编码规则 |
| **安全双层防护** | 服务端敏感词表 + 用户自定义避雷词，前端脱敏打码 + prompt 硬约束 |
| **双界面** | Web UI（拖拽上传、无图模式、审稿面板）+ CLI 命令行 |
| **实用优先** | 8 种风格 × 7 种语言 × 自由字数区间 × emoji/标点开关 |

---

## 效果演示

见项目根目录 `demo.mp4`（简易示范，未展示全部功能）

---

## 快速开始

### 环境要求
- Python 3.10+
- `pip install -r requirements.txt`（含 `Pillow`、`scikit-learn`，用于封面主色提取与 emoji 色调建议）

### 配置密钥
复制 `.envexample` 为 `.env`，按需填写：
- `QWEN_API_KEY`：图片理解（VL）必需
- `DEEPSEEK_API_KEY`：使用 DeepSeek 生成文案时需要（也可只用通义千问文本，共用同一个千问 key）
- `CAPTION_PROVIDER`：`deepseek` 或 `qwen`，控制文案生成使用的模型

其他可选变量：`CAPTION_MAX_TOKENS`、`LLM_REQUEST_TIMEOUT`。根目录 `blocked_words.txt`（可从 `blocked_words.example.txt` 复制改名）为服务端敏感词表，一行一词，`#` 开头为注释。

### 启动网页版
```bash
uvicorn webapp.main:app --host 127.0.0.1 --port 8765
```
打开 `http://127.0.0.1:8765` 即可使用。

### 命令行版
```bash
# 单条文案（快速）
python main.py test.jpg --style 幽默风趣 --language en
# 三条候选（与网页版一致）
python test_vision.py test.jpg --three --style 文艺清新
# 查看可用后端
python main.py --list-providers
```

---

## 功能一览

### 图片理解与文案生成
- 支持 **1～9 张图片**，调用通义千问 VL 生成画面描述；多张图综合描述氛围与关系
- 支持 **DeepSeek / 通义千问** 两种文案生成后端，可随时切换
- 一次生成 **三条候选文案**；支持"换三条"（更高温度重新生成）
- 支持 **无图模式**（仅凭心情/关键词生成，跳过图片理解）

### 风格与格式控制
- **八种预设风格**：幽默风趣、文艺清新、简洁干练、歌词感、生活随记、旅行手记、玩梗整活、种草安利
- **七种输出语言**：简体中文、繁体中文、English、Français、日本語、한국어、中英混用
- **字数区间**：可设定最少/最多字符数，prompt 中做硬性约束
- **emoji / 标点开关**：允许或禁止使用 emoji 和标点符号
- **补充想法 + 引用灵感**：带示例 placeholder，直接填入自由文本即可
- **避雷词**：用户输入 + 服务端词表合并，双层防护

### 安全与校验
- 敏感词脱敏：服务端 `blocked_words.txt` + 用户自定义词表合并，命中替换为星号
- 图片文件头校验：防止非图片文件浪费 VL 调用额度
- 单图 ≤10MB，最多 9 张

---

## Agent 能力

> 这是区别于"简单调 API"的核心设计：在基础生成流程上构建了一个轻量 Agent 闭环。

### 自评审 + 不达标重试

生成完成后，**后台异步调用模型**扮演审稿人（不阻塞文案返回），从四个维度逐条打分（每项 0-10）：

| 维度 | 检查内容 |
|---|---|
| 避雷合规 | 是否完全避开避雷词与敏感表达 |
| 字数合规 | 是否严格落在设定的字符数区间 |
| 质量创意 | 是否自然流畅、有记忆点、符合社交平台调性 |
| 差异性 | 三条之间的角度/修辞/情绪是否有明显区分 |

若及格数 < 阈值（默认 ≥2 条，单条均分 ≥6），自动以更高温度 + diversify 模式后台重试一次。前端有 **"Agent 审稿"面板**展示每条的四维评分、✅/❌ 判定、审稿人点评。

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `AGENT_REVIEW_ENABLED` | `true` | 关闭后退化为固定流程 |
| `AGENT_REVIEW_PASS_THRESHOLD` | `2` | 三条中至少 N 条及格 |
| `AGENT_REVIEW_SCORE_THRESHOLD` | `6` | 单条均分 ≥ 此值算及格 |
| `AGENT_REVIEW_MAX_RETRIES` | `1` | 不达标最多重试次数 |

### 偏好记忆

> 与"配置缓存"的关键区别：历史偏好以**自然语言摘要**注入 prompt，由模型自主判断是否延续，代码不做"if 偏好==A then 默认选 A"的硬编码。

**工作流程**：
1. 每次操作记录到 `data/preference_history.json`：复制某条 = 采纳，换三条 = 未采纳
2. 下次生成前，读取最近记录拼接为摘要（如 _"最近 3 次生成中，2 次采纳了「幽默风趣」"_），作为**软参考**注入 prompt
3. Prompt 明确告知：**"仅供参考，以用户本次手动选择的风格为准"**
4. 前端以蓝色提示条展示记忆反馈

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `AGENT_MEMORY_ENABLED` | `true` | 设为 `false` 关闭 |
| `AGENT_MEMORY_MAX_ENTRIES` | `10` | 历史保留最大条数 |
| `AGENT_MEMORY_CONTEXT_ENTRIES` | `5` | 注入 prompt 时参考最近 N 条 |

---

## 大模型产品调研

本项目开发过程中对主流大模型厂商进行了产品调研与选型分析，以下是六家核心厂商的产品矩阵：

| 厂商 | 核心模型 | 代表性产品 | 关键能力 |
|---|---|---|---|
| **MiniMax** | M3 / M2.7 / M2.5 | MiniMax Code、海螺视频、星野 | 1M 超长上下文、Coding/Agent、视频生成、语音合成 |
| **智谱** | GLM-4 系列 | 智谱清言 Agent 平台、CodeGeeX、CogView | Agent 应用生态、代码生成、图像生成 |
| **Kimi** | Moonshot | Kimi 智能助手、Kimi Code、Kimi Claw | 超长上下文、文档深度分析、插件生态 |
| **OpenAI** | GPT-5.6 / GPT-4o / o 系列 | ChatGPT、Codex、GPT-Live | 多模态理解、推理链、实时语音、平台生态 |
| **Google** | Gemini 3 Pro | NotebookLM、Gemini | 多模态、长上下文、研究辅助 |
| **DeepSeek** | V3 / R1 / Coder | DeepSeek Chat | 高性价比中文生成、强推理、开源 |

### 本项目选型

| 角色 | 选用模型 | 理由 |
|---|---|---|
| 视觉理解 | Qwen VL | 中文场景视觉能力优秀，API 稳定 |
| 文案生成 | DeepSeek / Qwen | DeepSeek 中文文笔自然流畅、性价比高；Qwen 作备选 |
| Agent 审稿 | 复用文案生成后端 | 独立模型角色实现交叉评审，无需额外配置 |

项目后端通过 `CAPTION_PROVIDER` 实现可插拔设计，后续可无缝接入 Kimi、智谱 GLM-4 等模型。

---

## 架构与技术栈

| 层级 | 技术 |
|---|---|
| 后端框架 | FastAPI |
| 前端 | 原生 HTML/CSS/JS（无框架依赖） |
| 图片理解 | 通义千问 VL (`qwen-vl-plus`) |
| 文案生成 | DeepSeek / 通义千问文本（OpenAI 兼容接口，`llm/http_chat.py` 统一调用） |
| Agent 自评审 | `agent_review.py` |
| Agent 偏好记忆 | `agent_memory.py`（本地 JSON，轻量无数据库） |
| 图像分析 | Pillow + scikit-learn（KMeans 主色聚类） |

### 关键文件

```
config.py              环境变量与默认模型配置
prompts.py             风格映射、语言指令、提示词模板、偏好摘要拼接
vision_tools.py        多图 VL 调用（通义千问 DashScope）
llm/http_chat.py       通用 Chat Completions HTTP 请求
llm/caption.py         三条候选生成与解析（后端可插拔）
agent_review.py        审稿打分 + 不达标自动重试
agent_memory.py        风格偏好历史记录与自然语言摘要
safety.py              敏感词合并与脱敏
media_validate.py      上传图片魔数校验
image_color_utils.py   封面主色提取与冷暖倾向判断
webapp/main.py         Web API
webapp/static/*        前端页面
main.py                CLI 入口
test_agent_memory.py   偏好记忆单元测试（14 项）
test_vision.py         VL + 文案联调脚本
```

---

## 测试

```bash
python test_agent_memory.py          # 偏好记忆 14 项单元测试
python test_vision.py test.jpg       # VL + 文案快速联调
```

---

## 后续可扩展方向

### 多模型接入
- 接入 **Kimi API**：利用超长上下文分析用户历史发帖，深化个性化
- 接入 **智谱 GLM-4**：作为独立审稿 Agent，与 DeepSeek 形成异源交叉评审，提升审稿客观性
- 接入 **MiniMax M3**：1M 上下文 + Agent 能力，用于更长篇的内容策划与文案策略编排

### 应用场景扩展
- **商用广告文案**：面向电商详情页、营销海报、促销活动等场景，提供结构化文案模板（标题 + 卖点 + 行动号召）
- **多平台风格适配**：针对小红书（种草体）、微博（话题体）、抖音（短平快）自动调整语气与格式
- **场景自动识别**：基于 VL 结果判断旅行/美食/自拍/宠物等场景，智能推荐风格

### 工程化升级
- Function Calling：让模型自主调用字数统计、敏感词检查等工具
- 多用户账号体系与偏好隔离
- 端侧本地部署（Ollama / ONNX），满足数据隐私需求

---

## 许可证

MIT
