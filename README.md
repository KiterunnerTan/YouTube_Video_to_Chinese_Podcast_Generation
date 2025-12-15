# AI Video to Audio - 视频转中文播客工具

一个将YouTube视频转换为自然流畅的中文播客音频的AI应用。支持完整流程：视频下载 → ASR转译 → AI翻译润色 → TTS生成中文语音。

## 功能特性

- 🎥 **YouTube视频下载**：支持cookie认证，可下载受保护的视频
- 🎙️ **ASR转译**：
  - Qwen3-ASR-Flash：快速高质量语音识别
  - Paraformer：支持说话人分离（需配置OSS）
- 🤖 **AI翻译**：Gemini 2.5 Pro智能翻译，自动添加语气词使对话更自然
- 🔊 **TTS语音生成**：Gemini 2.5 Preview高质量中文语音合成
- 🎵 **智能分段**：自动按时长分段处理，保持上下文连贯
- 💾 **中间结果保存**：保存ASR、翻译、音频片段等中间结果，便于调试
- 👥 **说话人分离**：自动识别不同说话人，生成更自然的多人对话播客

## 工作流程

```
YouTube视频 → ASR转译(Qwen3/Paraformer) → 文本预处理与分段
    ↓
翻译(Gemini + 语气词) → TTS生成(Gemini) → 音频合成 → 最终中文播客
```

## 安装

### 1. 克隆项目

```bash
git clone <repository-url>
cd ai_vedioToAudio
```

### 2. 创建虚拟环境并安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

**注意**：需要安装ffmpeg（用于音频处理）

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# 下载并安装：https://ffmpeg.org/download.html
```

### 3. 配置环境变量

复制配置模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的API密钥：

```env
# 阿里云百炼 DashScope API Key (用于 Qwen3-ASR 和 Paraformer)
DASHSCOPE_API_KEY=your_dashscope_api_key

# Google Gemini API Key (用于翻译和TTS)
GEMINI_API_KEY=your_gemini_api_key

# 代理设置 (在中国大陆访问 Google 服务时需要)
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890

# 处理配置
SEGMENT_DURATION_MINUTES=10
BATCH_SIZE=3
SAVE_INTERMEDIATE_RESULTS=true

# 阿里云OSS配置 (可选，用于说话人分离功能)
# 如果需要使用Paraformer的说话人分离功能，需要配置以下信息
OSS_ACCESS_KEY_ID=your_oss_access_key_id
OSS_ACCESS_KEY_SECRET=your_oss_access_key_secret
OSS_BUCKET_NAME=your_bucket_name
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

#### 获取API密钥

1. **阿里云百炼 DashScope API Key**：
   - 访问 [阿里云百炼控制台](https://dashscope.console.aliyun.com/)
   - 开通服务并创建API Key
   - 支持 Qwen3-ASR-Flash 和 Paraformer 模型

2. **Google Gemini API**：
   - 访问 [Google AI Studio](https://ai.google.dev/)
   - 创建API Key

3. **阿里云OSS配置（可选，用于说话人分离）**：
   - 访问 [阿里云OSS控制台](https://oss.console.aliyun.com/)
   - 创建Bucket
   - 在 [RAM控制台](https://ram.console.aliyun.com/) 获取AccessKey

4. **代理设置（中国大陆用户）**：
   - 如果你在中国大陆，需要配置代理才能访问Google服务
   - 使用Clash、V2Ray等工具，获取本地代理端口（通常是7890或7897）

## 使用方法

### 完整流程（一键运行）

**重要**：记得先激活虚拟环境！

```bash
# 激活虚拟环境
source venv/bin/activate

# 方案1：使用Paraformer（推荐，支持说话人分离）
python main.py full-pipeline <video_file> -o podcast.mp3

# 方案2：不使用说话人分离（无需OSS配置）
python main.py full-pipeline <video_file> -o podcast.mp3 --no-diarization

# 指定说话人数量（可选）
python main.py full-pipeline <video_file> -o podcast.mp3 -s 2
```

**参数说明**：
- `<video_file>`：本地视频/音频文件路径
- `-o`：输出音频文件路径（可选，默认保存在output/final/）
- `--enable-diarization / --no-diarization`：是否启用说话人分离（默认启用）
- `-s`：预期说话人数量（可选，不指定则自动检测）
- `-l`：语言提示（可选，默认：zh en）

### 分步执行

#### 步骤1：下载YouTube视频

```bash
# 激活虚拟环境
source venv/bin/activate

# 下载视频
python main.py download <youtube_url>

# 使用cookie下载（针对需要登录的视频）
python main.py download <youtube_url> -c cookies.txt

# 仅下载音频
python main.py download <youtube_url> -a
```

**获取cookies.txt**：
- 安装Chrome扩展：[Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/)
- 访问YouTube并登录
- 点击扩展图标导出cookies.txt

#### 步骤2：ASR转译

```bash
# 使用Qwen3-ASR（快速，无说话人分离）
python main.py asr <video_file> -l zh -l en -o asr_result.json
```

**参数说明**：
- `<video_file>`：本地视频/音频文件路径
- `-l`：语言提示（可多次指定，默认：zh en）
- `-o`：输出JSON文件路径（可选）

**注意**：如需说话人分离，建议直接使用 `full-pipeline` 命令

#### 步骤3：处理ASR结果

```bash
python main.py process asr_result.json -o processed.json
```

#### 步骤4：翻译

```bash
python main.py translate processed.json -o translations.json
```

#### 步骤5：生成语音

```bash
python main.py tts translations.json -o ./audio_segments -m manifest.json
```

#### 步骤6：合并音频

```bash
python main.py merge manifest.json -o final_podcast.mp3
```

## 项目结构

```
ai_vedioToAudio/
├── main.py                 # CLI主入口
├── config.py               # 配置管理
├── requirements.txt        # Python依赖
├── .env.example            # 配置模板
├── .env                    # 实际配置（需自行创建）
├── README.md               # 本文档
├── utils/                  # 工具模块
│   ├── youtube_downloader.py   # YouTube下载
│   ├── asr_processor.py        # 通义听悟ASR
│   ├── text_processor.py       # 文本预处理
│   ├── translator.py           # Gemini翻译
│   ├── tts_generator.py        # Gemini TTS
│   └── audio_merger.py         # 音频合成
└── output/                 # 输出目录
    ├── downloads/          # 下载的视频
    ├── asr_results/        # ASR结果
    ├── translations/       # 翻译结果
    ├── audio_segments/     # 音频片段
    └── final/              # 最终音频
```

## 技术实现细节

### 分段策略

- **分段时长**：每10分钟为一段（可配���）
- **批量翻译**：每次翻译时会携带前后段作为上下文（前1段+当前+后1段）
- **优势**：既能保持上下文连贯，又能避免API限制和单点故障

### 翻译优化

- 使用Gemini 2.5 Pro进行智能翻译
- 自动添加语气词："嗯"、"哦"、"其实"、"那么"等
- 保持对话自然性和播客风格

### 错误处理

- **失败即停**：任何环节失败立即报错，不继续执行
- **中间结果保存**：所有步骤的中间结果都会保存，便于排查问题

## 独立使用YouTube下载器

```bash
cd utils
python youtube_downloader.py <youtube_url> -c cookies.txt -o ../output/downloads
```

## 常见问题

### Q: 如何启用说话人分离功能？

A: 说话人分离功能默认启用。需要完成以下配置：
1. 在 `.env` 文件中配置阿里云OSS相关信息（OSS_ACCESS_KEY_ID、OSS_ACCESS_KEY_SECRET、OSS_BUCKET_NAME）
2. 使用 `full-pipeline` 命令时会自动使用Paraformer模型进行说话人分离
3. 如果不需要说话人分离，可以使用 `--no-diarization` 参数

### Q: 运行命令时提示找不到模块？

A: 请确保已激活虚拟环境：
```bash
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

### Q: 中国大陆访问Gemini API失败？

A: 需要配置代理：
1. 启动代理工具（Clash、V2Ray等）
2. 在 `.env` 文件中设置 `HTTP_PROXY` 和 `HTTPS_PROXY`
3. 端口号通常是7890或7897，具体查看你的代理工具设置

### Q: Gemini TTS支持哪些语音？

A: 默认使用 `Aoede` 语音。可在代码中修改 `voice_name` 参数，支持的语音列表见 [Gemini文档](https://ai.google.dev/gemini-api/docs/models)。

### Q: 翻译速度慢怎么办？

A: 可以调整 `.env` 中的 `SEGMENT_DURATION_MINUTES`，减小分段时长会增加分段数，但单次翻译更快。

### Q: API费用如何？

A:
- **阿里云百炼 DashScope**：按调用次数/时长计费，具体见[定价说明](https://dashscope.console.aliyun.com/)
- **Gemini API**：有免费额度，具体见[Google定价](https://ai.google.dev/pricing)
- **阿里云OSS**：按存储和流量计费，具体见[OSS定价](https://www.aliyun.com/price/product#/oss/detail)

## 开发计划

- [x] 集成阿里云OSS自动上传（已完成）
- [x] 支持说话人分离（已完成）
- [ ] 支持多种TTS语音选择
- [ ] 支持断点续传
- [ ] 添加进度条显示
- [ ] Web UI界面
- [ ] 支持更多视频平台
- [ ] 批量处理功能

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！

## 联系方式

如有问题或建议，请提交Issue。
