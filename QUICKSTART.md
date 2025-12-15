# 快速开始指南

## ✅ 已完成的设置

1. ✓ Python 虚拟环境已创建 (`venv/`)
2. ✓ 所有依赖已安装
3. ✓ ffmpeg 已安装并可用
4. ✓ .env 配置文件已创建

## 🔑 API密钥状态

当前配置的API密钥：
- ✓ Gemini API Key: 已配置
- ✓ 通义听悟 App Key: 已配置
- ⚠️ 阿里云 AccessKey: **需要补充**（如果通义听悟API需要）

## 📋 待补充的配置

请检查 `.env` 文件中的以下字段是否需要补充：

```bash
ALIYUN_ACCESS_KEY_ID=your_aliyun_access_key_id
ALIYUN_ACCESS_KEY_SECRET=your_aliyun_access_key_secret
```

如果通义听悟只需要 AppKey 即可工作，这两项可以暂时忽略。

## 🚀 开始使用

### 1. 激活虚拟环境

每次使用前需要激活虚拟环境：

```bash
source venv/bin/activate
```

### 2. 查看所有可用命令

```bash
python main.py --help
```

### 3. 下载YouTube视频（可选）

如果需要从YouTube下载视频：

```bash
# 下载视频
python main.py download "<youtube_url>"

# 使用cookie下载（针对需要登录的视频）
python main.py download "<youtube_url>" -c cookies.txt

# 仅下载音频
python main.py download "<youtube_url>" -a
```

**获取cookies.txt**：
- 安装Chrome扩展：[Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/)
- 访问YouTube并登录
- 点击扩展图标导出cookies.txt

### 4. 完整流程示例

假设你已经有一个视频文件，并上传到了某个公开的URL：

```bash
python main.py full-pipeline video.mp4 --file-url https://your-oss-url/video.mp4 -o podcast.mp3
```

**重要提示**：
- `video.mp4` 是本地视频文件路径
- `--file-url` 参数是视频在云存储上的公开访问URL（通义听悟需要）
- 如果没有云存储，需要先将视频上传到阿里云OSS或其他云服务

### 5. 分步执行示例

如果想分步骤执行，可以：

```bash
# 步骤1：ASR转译（需要公开URL）
python main.py asr https://your-oss-url/video.mp4 -o asr_result.json

# 步骤2：处理ASR结果
python main.py process asr_result.json -o processed.json

# 步骤3：翻译
python main.py translate processed.json -o translations.json

# 步骤4：生成语音
python main.py tts translations.json -m manifest.json

# 步骤5：合并音频
python main.py merge manifest.json -o final_podcast.mp3
```

## 🔍 测试配置

### 测试YouTube下载

```bash
python main.py download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -a
```

### 测试Gemini API

您可以尝试翻译功能测试Gemini API是否正常：

```bash
# 需要先有处理好的ASR结果
python main.py translate output/asr_results/processed_xxx.json
```

## ⚠️ 常见问题

### 1. 通义听悟API认证问题

如果遇到认证错误，请确认：
- 通义听悟 AppKey 是否正确
- 是否需要补充阿里云 AccessKey ID 和 Secret
- 查看[通义听悟文档](https://help.aliyun.com/zh/tingwu/)了解认证方式

### 2. 视频需要公开URL

通义听悟API要求视频必须有公开访问URL。如果没有：
- 选项A：上传到阿里云OSS获取公开URL
- 选项B：使用其他云存储服务（腾讯云COS、AWS S3等）
- 选项C：等待后续版本集成OSS自动上传功能

### 3. Gemini API配额

- Gemini API有免费额度限制
- 如果遇到配额错误，请检查[Google AI Studio](https://ai.google.dev/)账户状态
- 翻译和TTS会消耗配额，注意控制使用量

## 📊 输出文件位置

所有中间结果和最终输出保存在 `output/` 目录：

```
output/
├── downloads/          # YouTube下载的视频
├── asr_results/        # ASR转译结果和处理后的分段
├── translations/       # 翻译结果
├── audio_segments/     # TTS生成的音频片段
└── final/             # 最终合成的播客音频
```

## 🎯 下一步

1. 确认API密钥是否完整
2. 准备测试视频
3. 将测试视频上传到云存储获取公开URL
4. 运行完整流程测试

## 💡 提示

- 第一次运行建议使用短视频（<5分钟）测试
- 检查每个步骤的输出，确保流程正常
- 所有中间结果都会保存，方便调试
- 如遇到问题，查看详细错误信息

祝您使用愉快！🎉
