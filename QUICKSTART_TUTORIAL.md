# 快速开始指南

本指南将帮助你在5分钟内完成项目配置并运行第一个完整的视频转播客流程。

## 前置要求

- Python 3.8+
- ffmpeg（音频处理）
- 稳定的网络连接

## 1. 安装步骤

### 1.1 克隆项目并进入目录

```bash
git clone <repository-url>
cd ai_vedioToAudio
```

### 1.2 安装 ffmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows - 访问 https://ffmpeg.org/download.html 下载
```

### 1.3 创建虚拟环境并安装依赖

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

## 2. 配置环境变量

### 2.1 复制配置模板

```bash
cp .env.example .env
```

### 2.2 编辑 `.env` 文件

打开 `.env` 文件，填入你的API密钥：

```env
# 必填：阿里云百炼 DashScope API Key
DASHSCOPE_API_KEY=你的dashscope_api_key

# 必填：Google Gemini API Key
GEMINI_API_KEY=你的gemini_api_key

# 中国大陆用户必填：代理设置
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

### 2.3 获取API密钥

#### DashScope API Key（阿里云百炼）

1. 访问 https://dashscope.console.aliyun.com/
2. 登录阿里云账号
3. 点击右上角头像 → API-KEY管理
4. 创建新的API Key并复制

#### Gemini API Key

1. 访问 https://ai.google.dev/
2. 点击 "Get API key in Google AI Studio"
3. 创建新项目并生成API Key

#### 代理设置（中国大陆用户）

1. 启动你的代理工具（Clash、V2Ray等）
2. 查看本地代理端口（通常是7890或7897）
3. 在`.env`文件中设置对应的端口号

## 3. 运行第一个示例

### 方案A：使用本地视频/音频文件（推荐新手）

如果你已经有一个视频或音频文件：

```bash
# 激活虚拟环境（如果还没激活）
source venv/bin/activate

# 运行完整流程（不使用说话人分离）
python main.py full-pipeline your_video.mp4 -o my_podcast.mp3 --no-diarization
```

**参数说明**：
- `your_video.mp4` - 你的视频或音频文件路径
- `-o my_podcast.mp3` - 输出的播客音频文件
- `--no-diarization` - 不使用说话人分离（无需配置OSS）

### 方案B：使用说话人分离（推荐多人对话）

如果你的视频是多人对话，推荐使用说话人分离功能：

#### 3.1 配置阿里云OSS（一次性配置）

1. 访问 https://oss.console.aliyun.com/
2. 创建一个Bucket（例如：ai-podcast）
3. 访问 https://ram.console.aliyun.com/manage/ak 获取AccessKey
4. 在 `.env` 文件中添加OSS配置：

```env
OSS_ACCESS_KEY_ID=你的access_key_id
OSS_ACCESS_KEY_SECRET=你的access_key_secret
OSS_BUCKET_NAME=ai-podcast
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

#### 3.2 运行带说话人分离的完整流程

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行完整流程（使用说话人分离）
python main.py full-pipeline your_video.mp4 -o my_podcast.mp3

# 如果知道说话人数量，可以指定
python main.py full-pipeline your_video.mp4 -o my_podcast.mp3 -s 2
```

### 方案C：从YouTube下载并转换

```bash
# 激活虚拟环境
source venv/bin/activate

# 1. 下载YouTube视频
python main.py download "https://www.youtube.com/watch?v=VIDEO_ID" -a

# 2. 运行完整流程
python main.py full-pipeline output/downloads/downloaded_file.m4a -o podcast.mp3 --no-diarization
```

## 4. 查看结果

处理完成后，你会在以下位置找到输出文件：

- **最终播客音频**：`output/final/` 或你指定的输出路径
- **ASR转译结果**：`output/asr_results/`
- **翻译结果**：`output/translations/`
- **音频片段**：`output/audio_segments/`

## 5. 常见问题排查

### 问题1：提示找不到模块

**原因**：未激活虚拟环境

**解决**：
```bash
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

### 问题2：Gemini API调用失败

**原因**：中国大陆用户未配置代理

**解决**：
1. 确保代理工具正在运行
2. 检查 `.env` 文件中的代理端口是否正确
3. 测试代理：`curl -x http://127.0.0.1:7890 https://www.google.com`

### 问题3：OSS上传失败

**原因**：OSS配置不正确

**解决**：
1. 检查 `.env` 中的OSS配置
2. 确认Bucket已创建
3. 或者使用 `--no-diarization` 跳过说话人分离

### 问题4：处理速度慢

**原因**：视频太长或网络问题

**优化建议**：
- 调整 `.env` 中的 `SEGMENT_DURATION_MINUTES`（默认10分钟）
- 使用音频文件而非视频文件
- 检查网络连接

## 6. 下一步

恭喜！你已经成功运行了第一个播客转换。

接下来你可以：

1. **查看详细文档**：阅读 `README.md` 了解更多功能
2. **分步执行**：学习如何单独运行每个步骤（ASR、翻译、TTS等）
3. **自定义配置**：调整分段时长、批处理大小等参数
4. **探索高级功能**：尝试不同的语音、优化翻译质量等

## 需要帮助？

- 查看 `README.md` 获取完整文档
- 查看 `PROXY-SETUP.md` 了解代理配置
- 提交Issue：https://github.com/<your-repo>/issues

祝使用愉快！
