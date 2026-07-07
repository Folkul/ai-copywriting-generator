# 配图说 —— 上传照片，AI 帮你写朋友圈文案

上传 1～9 张图片，AI 先看懂画面内容，再按你选的风格生成三条候选文案，直接复制发圈。也支持不传图、只写心情关键词的无图模式。

---

## 为什么做这个

发朋友圈/小红书时"配文比拍照还难"是个很真实的小烦恼——图拍好了，坐在那想文案想半天，写出来又觉得没那味儿。配图说想做的就是把这个过程自动化：看图 → 选风格 → 生成 → 挑一条发出去，整个流程不超过一分钟。

---

## 效果演示

见项目根目录 `demo.mp4`

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

## 完整功能一览

### 图片理解与文案生成
- 支持 **1～9 张图片**，调用通义千问 VL 生成画面描述；多张图会综合描述氛围与关系
- 支持 **DeepSeek / 通义千问** 两种文案生成后端，可随时切换
- 一次生成 **三条候选文案**；支持"换三条"（同一画面描述，更高温度重新生成）
- 支持 **无图模式**（仅凭心情/关键词生成，跳过图片理解）

### 文案风格与格式控制
- **八种预设风格**：幽默风趣、文艺清新、简洁干练、歌词感、生活随记、旅行手记、玩梗整活、种草安利
- **七种输出语言**：简体中文 / 繁体中文 / English / Français / 日本語 / 한국어 / 中英混用
- **字数区间**：可设定最少/最多字符数，prompt 中做硬性约束
- **emoji / 标点开关**：允许或禁止使用 emoji 和标点符号
- **补充想法 + 引用灵感**：带示例 placeholder，直接填入自由文本即可，不需删默认内容
- **避雷词**：用户输入 + 服务端词表合并，双层防护（前端脱敏打码 + prompt 硬性约束模型避开）

### 安全与校验
- 敏感词脱敏：服务端 `blocked_words.txt` + 用户自定义词表合并，命中替换为星号
- 图片文件头校验：防止非图片文件浪费 VL 调用额度
- 单图 ≤10MB，最多 9 张

### Agent 辅助能力
- **自评审**：生成后自动调模型审稿，从避雷合规、字数合规、创意质量、差异性四个维度打分，不达标自动重试一次；前端有评审面板展示打分细节
- **偏好记忆**：自动记录风格采纳/拒绝历史，下次生成时以自然语言摘要形式作为软参考注入 prompt，模型自主判断是否延续（而非代码直接决定默认值）；前端有蓝色提示条反馈
- 两个机制均可通过环境变量关闭，关后退化为基础流程，不影响核心功能

### 双界面
- **Web UI**：拖拽/多选/文件夹上传、无图模式、高级设置面板、Agent 审稿面板、偏好记忆提示条、localStorage 偏好持久化
- **CLI**：`main.py` 支持基本参数（单条文案）；`test_vision.py --three` 提供与网页一致的三候选体验

---

## 架构与技术栈

| 层级 | 技术 |
|---|---|
| 后端框架 | FastAPI |
| 前端 | 原生 HTML/CSS/JS（无框架依赖） |
| 图片理解 | 通义千问 VL (`qwen-vl-plus`) |
| 文案生成 | DeepSeek / 通义千问文本（OpenAI 兼容接口，通过 `llm/http_chat.py` 统一调用） |
| Agent 自评审 | `agent_review.py` |
| Agent 偏好记忆 | `agent_memory.py`（本地 JSON 文件，无数据库） |
| 图像分析 | Pillow + scikit-learn（KMeans 主色聚类，前端展示色块 + 可选的 emoji 色调建议） |

### 关键文件

```
config.py              环境变量与默认模型配置
prompts.py             风格映射、语言指令、提示词模板、偏好摘要拼接
vision_tools.py        多图 VL 调用（通义千问 DashScope）
llm/http_chat.py       通用 Chat Completions HTTP 请求
llm/caption.py         三条候选生成与解析
agent_review.py        审稿打分 + 不达标自动重试
agent_memory.py        风格偏好历史记录与自然语言摘要
safety.py              敏感词合并与脱敏
media_validate.py      上传图片魔数校验
image_color_utils.py   封面主色提取与冷暖倾向判断
webapp/main.py         Web API（/api/full、/api/regenerate、/api/feedback、/api/review）
webapp/static/*        前端页面（index.html、app.js、styles.css）
main.py                CLI 入口
test_agent_memory.py   偏好记忆单元测试（14 项）
test_vision.py         VL + 文案联调脚本
```

---

## Agent 能力

除了基础的"生成三条文案"，系统还有两个辅助机制，分别用于提升**生成质量的稳定性**和**长期使用的贴合度**：

### 自评审 + 不达标重试

生成完成后，**后台异步调用一次模型**扮演审稿人（不阻塞文案返回），从四个维度逐条打分（每项 0-10）：

| 维度 | 检查内容 |
|---|---|
| 避雷合规 | 是否完全避开避雷词与敏感表达 |
| 字数合规 | 是否严格落在设定的字符数区间 |
| 质量创意 | 是否自然流畅、有记忆点、符合朋友圈调性 |
| 差异性 | 三条之间的角度/修辞/情绪是否有明显区分 |

若及格数 < 阈值（默认 ≥2 条，单条均分 ≥6），自动以更高温度 + diversify 模式后台重试一次。前端有 **"Agent 审稿"面板**（文案出现后几秒自动弹出）展示每条的四维评分、✅/❌ 判定、审稿人点评和是否触发重试。

#### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AGENT_REVIEW_ENABLED` | `true` | 设为 `false` 可关闭，退化为原有固定流程 |
| `AGENT_REVIEW_PASS_THRESHOLD` | `2` | 三条中至少 N 条及格才算通过 |
| `AGENT_REVIEW_SCORE_THRESHOLD` | `6` | 单条四项均分 ≥ 此值算及格 |
| `AGENT_REVIEW_MAX_RETRIES` | `1` | 不达标最多重试几次（0 = 不重试） |

评审调用失败或返回格式异常时**静默跳过**，不影响候选文案的正常返回。

### 偏好记忆

> 与"配置缓存"的关键区别：历史偏好以**自然语言摘要**形式注入 prompt，由模型自主判断是否延续，代码不做任何 "if 偏好==A then 默认选中A" 的判断。

**如何工作**：
1. 每次操作被记录到本地 `data/preference_history.json`：复制某条 = 采纳，点击换三条 = 未采纳；自动裁剪到最近 10 条
2. 下次生成前，读取最近 5 条拼接为摘要（如 _"最近 3 次生成中，2 次采纳了「幽默风趣」风格，1 次在「文艺清新」风格下选择了换三条"_），作为**软参考**注入 prompt
3. Prompt 明确告知模型：**"仅供参考，以用户本次手动选择的风格为准"**
4. 前端以蓝色提示条 _"🧠 本次生成参考了你最近的风格偏好"_ 展示这一过程

#### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AGENT_MEMORY_ENABLED` | `true` | 设为 `false` 可关闭偏好记忆 |
| `AGENT_MEMORY_MAX_ENTRIES` | `10` | 历史文件保留的最大条数 |
| `AGENT_MEMORY_CONTEXT_ENTRIES` | `5` | 注入 prompt 时参考最近 N 条 |

历史文件损坏或不存在时静默跳过，不影响生成流程。CLI 命令默认不启用记忆（一次性调用场景下历史参考意义有限）。

---

## 测试

```bash
python test_agent_memory.py          # 偏好记忆 14 项单元测试
python test_vision.py test.jpg       # VL + 文案快速联调
```

`test_agent_memory.py` 覆盖：历史写入/读取、自动裁剪、禁用降级、文件损坏容错、未知风格 slug 回退、软参考措辞验证。

---

## 后续可扩展方向

- 场景自动识别（旅行/美食/自拍/产品）辅助风格推荐
- Function Calling：让模型自主决定何时调用敏感词检查、字数统计等工具
- 多用户偏好隔离（当前为单机本地记忆，未做账号体系）
