# Qwen3-ASR 方案使用指南

## ✅ 实现完成！

我们已经成功将ASR模块从通义听悟切换到**阿里云百炼 Qwen3-ASR-Flash**，实现了**超简单**的本地文件处理方案。

---

## 🎯 核心优势

### ✅ 无需OSS上传
- **直接处理本地文件**，无需上传到云存储
- 使用 `file://` 协议，自动读取本地视频/音频
- 节省OSS存储费用和配置复杂度

### ✅ 智能音频切分
- 自动检测文件时长
- 超过3分钟自动切分为多段
- 并行识别，提升效率

### ✅ 强大的多语言支持
- 支持11种语言（中英法德俄意西葡日韩阿）
- 支持中文方言（四川话、闽南语、吴语、粤语）
- 自动语言检测和切换

### ✅ 极致简单
- 只需要**一个API Key**：DashScope API Key
- 无需阿里云 AccessKey/Secret
- 配置项极少

---

## 📦 已完成的更新

### 1. 核心模块
- ✅ `utils/asr_processor.py` - 重写为 Qwen3ASRProcessor
  - `AudioSplitter` - 自动音频切分（3分钟/段）
  - `Qwen3ASRProcessor` - DashScope API 集成
  - 支持本地文件直接处理

### 2. 配置文件
- ✅ `config.py` - 更新API配置
  - `DASHSCOPE_API_KEY` - 替代旧的通义听悟配置
  - 简化验证逻辑

- ✅ `.env` - 简化配置
  ```env
  DASHSCOPE_API_KEY=sk-d086548cbf5545c29159fb5bffb2e9e1
  GEMINI_API_KEY=AIzaSyBdypFvt_4lct0CDjTG4ZVwefMHfyBpv2o
  ```

### 3. CLI命令
- ✅ `main.py` - 更新ASR命令
  ```bash
  # 旧版（需要URL）
  python main.py asr <file_url> -o output.json

  # 新版（本地文件）✨
  python main.py asr video.mp4 -o output.json
  ```

### 4. 依赖管理
- ✅ `requirements.txt` - 添加 dashscope>=1.20.0
- ✅ 已安装到虚拟环境

### 5. 文本处理
- ✅ `text_processor.py` - 适配Qwen3-ASR输出格式

---

## 🚀 使用方式

### 方式1：单独ASR识别

```bash
# 激活虚拟环境
source venv/bin/activate

# 处理本地视频/音频文件
python main.py asr video.mp4

# 指定语言
python main.py asr video.mp4 -l zh -l en

# 自定义输出路径
python main.py asr video.mp4 -o my_result.json
```

### 方式2：完整流程

```bash
# 一键运行完整流程（无需URL！）
python main.py full-pipeline video.mp4 -o podcast.mp3

# 指定语言
python main.py full-pipeline video.mp4 -l zh -l en -o podcast.mp3
```

### 方式3：结合YouTube下载

```bash
# Step 1: 下载YouTube视频
python main.py download "<youtube_url>" -a

# Step 2: ASR识别下载的文件
python main.py asr output/downloads/video.mp4

# Step 3: 完整流程
python main.py full-pipeline output/downloads/video.mp4 -o podcast.mp3
```

---

## 🔧 工作原理

### 处理短视频（≤3分钟）
```
本地视频 → Qwen3-ASR直接识别 → 保存结果
```

### 处理长视频（>3分钟）
```
本地视频 → 检测时长 → 自动切分为3分钟段
         ↓
    Segment 1 (0-3分钟)  \
    Segment 2 (3-6分钟)   |→ 并行识别
    Segment 3 (6-9分钟)  /
         ↓
    合并所有段的结果 → 保存完整结果
```

### 输出格式
```json
{
  "source_file": "/path/to/video.mp4",
  "total_segments": 5,
  "model": "qwen-audio-turbo",
  "segments": [
    {
      "segment_id": 0,
      "start_time_ms": 0,
      "end_time_ms": 180000,
      "transcription": {
        "text": "识别的文本内容...",
        "...": "..."
      }
    },
    ...
  ]
}
```

---

## ⚙️ 高级配置

### 修改分段时长

在 `utils/asr_processor.py` 中修改：
```python
processor = Qwen3ASRProcessor(
    api_key=Config.DASHSCOPE_API_KEY,
    segment_duration_seconds=120  # 改为2分钟/段
)
```

### 支持的语言提示

```python
language_hints = [
    'zh',     # 中文
    'en',     # 英文
    'ja',     # 日语
    'ko',     # 韩语
    'fr',     # 法语
    'de',     # 德语
    'ru',     # 俄语
    'it',     # 意大利语
    'es',     # 西班牙语
    'pt',     # 葡萄牙语
    'ar',     # 阿拉伯语
]
```

---

## 📊 性能对比

| 维度 | 旧方案（通义听悟） | 新方案（Qwen3-ASR）✨ |
|------|------------------|---------------------|
| 文件输入 | ❌ 需要公开URL | ✅ 支持本地文件 |
| OSS上传 | ❌ 必须上传 | ✅ 无需上传 |
| 配置复杂度 | ⚠️ 需要3个密钥 | ✅ 只需1个密钥 |
| 语言支持 | ⚠️ 较少 | ✅ 11种语言 |
| 基座模型 | 通义实验室 | ✅ Qwen3-Omni（最新） |
| 特色功能 | 标准ASR | ✅ 歌声识别、极端环境鲁棒 |
| 使用复杂度 | ⚠️ 中等 | ✅ **极简** |

---

## 🎬 完整示例

### 场景：处理60分钟YouTube视频

```bash
# 1. 下载视频
python main.py download "https://youtube.com/watch?v=xxx" -a
# 输出：output/downloads/video.mp4

# 2. ASR识别（自动切分为20段×3分钟）
python main.py asr output/downloads/video.mp4
# 输出：output/asr_results/qwen_asr_20251214_150000.json

# 3. 处理分段（重组为10分钟段）
python main.py process output/asr_results/qwen_asr_20251214_150000.json
# 输出：output/asr_results/processed_20251214_150000.json

# 4. 翻译
python main.py translate output/asr_results/processed_20251214_150000.json
# 输出：output/translations/translations_20251214_150000.json

# 5. TTS生成
python main.py tts output/translations/translations_20251214_150000.json
# 输出：output/audio_segments/manifest_20251214_150000.json

# 6. 合并音频
python main.py merge output/audio_segments/manifest_20251214_150000.json -o podcast.mp3
# 输出：podcast.mp3
```

**或者一键运行：**
```bash
python main.py full-pipeline output/downloads/video.mp4 -o podcast.mp3
```

---

## ⚠️ 注意事项

### 1. API配额
- Qwen3-ASR有QPS限制（100 QPS）
- 对于播客制作完全足够
- 如需高并发，建议分批处理

### 2. 文件格式
- 支持常见格式：mp4, mp3, wav, m4a等
- 由ffmpeg自动处理格式转换
- 推荐：16kHz单声道，可减少处理时间

### 3. 成本控制
- 只有ASR和Gemini API费用
- 无OSS存储费用
- 建议先用短视频测试

---

## 🆚 与其他方案对比

### vs Fun-ASR-MTL
- ❌ Fun-ASR-MTL 不支持本地文件
- ✅ Qwen3-ASR支持本地文件，更简单

### vs Paraformer
- ❌ Paraformer 不支持本地文件
- ✅ Qwen3-ASR支持本地文件，功能更强

### vs Qwen3-ASR-Flash-Filetrans
- ⚠️ Filetrans 支持12小时文件，但需要URL
- ✅ Qwen3-ASR-Flash 支持本地文件，自动切分无限制

---

## 📝 总结

Qwen3-ASR方案完美实现了您"有无更简单方式"的需求：

✅ **超简单** - 只需一个API Key
✅ **本地化** - 无需OSS上传
✅ **智能化** - 自动切分、合并
✅ **强大** - Qwen3基座，11种语言
✅ **完整** - 配合Gemini实现完整播客制作流程

现在您可以开始使用了！🎉

---

## 🔗 相关链接

- [DashScope官方文档](https://dashscope.aliyun.com/)
- [Qwen3-ASR-Flash模型介绍](https://www.datalearner.com/ai-models/pretrained-models/Qwen3-ASR-Flash)
- [阿里云百炼平台](https://bailian.aliyun.com/)
