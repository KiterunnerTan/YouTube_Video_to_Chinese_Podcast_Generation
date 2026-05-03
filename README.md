# YouTube Video to Chinese Podcast Generation

一键将英文 YouTube 视频转译为中文双人播客节目，自动完成：YouTube 下载 → 语音识别 → 中文翻译 → 双语主持人 TTS → 音乐拼接 → 节目文案生成。

最终产物是一个完整的、可直接发布的中文播客 MP3，配套节目介绍文案。

## ✨ 特性

- 🎬 **YouTube 自动下载**：支持 cookie 登录，处理需要会员/年龄验证的视频
- 🗣️ **多说话人 ASR**：阿里云 Paraformer / Qwen3-ASR，自动识别说话人切分
- 🌏 **高质量翻译**：Google Gemini 2.5 Flash，强化口语化、情绪、节奏
- 🎙️ **双主持人 TTS**：MiniMax Speech 2.6 HD，男女声轮替对话
- 🎵 **专业音频拼接**：开场白 + 节目概要 + 主音频 + 片头/过渡/片尾音乐，带渐出效果
- 📝 **节目文案自动生成**：适合公众号、小宇宙等平台分发
- ♻️ **缓存机制**：翻译/TTS 结果缓存，失败可断点续传

## 🏗️ 节目结构

```
片头音乐(渐出) → 开场白 → 过渡音乐 → 节目概要 → 过渡音乐 → 主音频(双语对话) → 片尾音乐
```

| 部分     | 音量  | 倍速   | 说明           |
| -------- | ----- | ------ | -------------- |
| 开场白   | 2.6×  | 1.05×  | 克隆音色       |
| 节目概要 | 2.6×  | 1.05×  | 增强情绪与节奏 |
| 主音频   | 2.6×  | 1.05×  | 双语主持对话   |
| 音乐     | 0.4×  | 1.0×   | 2 秒渐出       |

## 🚀 快速开始

### 1. 安装依赖

```bash
# Python 依赖
pip install -r requirements.txt

# FFmpeg
brew install ffmpeg          # macOS
# 或
sudo apt-get install ffmpeg  # Linux
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env` 并填入：

```env
DASHSCOPE_API_KEY=...        # 阿里云百炼 (ASR)
GEMINI_API_KEY=...           # Google Gemini (翻译)
MINIMAX_API_KEY=...          # MiniMax (TTS)
MINIMAX_GROUP_ID=...

# 中国大陆访问 Google 需要代理
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897

# 可选：用 Paraformer 说话人分离需要 OSS
OSS_ACCESS_KEY_ID=...
OSS_ACCESS_KEY_SECRET=...
OSS_BUCKET_NAME=...
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

### 3. 编辑 `start_prompt.md`

```markdown
播客名字是{节目名}，嘉宾是{嘉宾名}。

YouTube URL: https://www.youtube.com/watch?v=xxxxxxxxxxx

当前要转译的cookie文件目录地址：{/path/to/cookie.txt}

音色配置: speaker_0:{Chinese (Mandarin)_Crisp_Girl}, speaker_1:{male-qn-jingying}
speaker数量: 2

基于以上信息，给我自动生成完整的播客节目！
```

参考 `start_prompt_example.md` 查看完整范例。

### 4. 一键生成

```bash
python generate.py
```

完成后产物在 `output/<播客名>/`：

- `podcast_final.mp3` — 最终播客音频
- `podcast_description.txt` — 节目介绍文案

## 🎤 音色推荐

**女声**

- `Chinese (Mandarin)_Crisp_Girl` — 清脆女声
- `Chinese (Mandarin)_Warm_Bestie` — 温暖好友
- `Chinese (Mandarin)_News_Anchor` — 新闻主播

**男声**

- `male-qn-jingying` — 精英男声
- `Chinese (Mandarin)_Reliable_Executive` — 可靠管理者
- `Chinese (Mandarin)_Gentleman` — 绅士

## 🛠️ 辅助脚本

- `regenerate_main_audio.py` — 仅替换音色重新生成主音频，复用已有的开场白/概要/音乐
- `regenerate_description.py` — 仅重新生成节目文案
- `test_voice_stability.py` — 音色稳定性测试

## 📁 项目结构

```
.
├── generate.py                          # 主入口
├── auto_generate_podcast.py             # 完整自动化流程
├── start_prompt.md                      # 用户配置（编辑这个）
├── config.py                            # 全局配置
├── utils/
│   ├── youtube_downloader.py            # YouTube 下载
│   ├── asr_processor.py                 # ASR 调度
│   ├── paraformer_asr.py                # 多说话人 ASR
│   ├── translator_v1_4.py               # 翻译引擎
│   ├── tts_generator_v1_4.py            # TTS 引擎
│   ├── audio_merger_with_music.py       # 音频拼接
│   ├── episode_summary_generator.py     # 节目概要
│   ├── podcast_description_generator.py # 节目文案
│   ├── voice_config_parser.py           # 音色解析
│   └── ...
├── music/                               # 片头/过渡/片尾素材
├── prologue/                            # 开场白素材
├── output/                              # 生成结果
└── requirements.txt
```

## 🔧 技术栈

- **ASR**：阿里云 DashScope Qwen3-ASR / Paraformer（说话人分离）
- **翻译**：Google Gemini 2.5 Flash
- **TTS**：MiniMax Speech 2.6 HD
- **音频处理**：FFmpeg
- **YouTube**：yt-dlp
- **运行环境**：Python 3.10+

## 📜 版本

- **v1.6**（当前）— 新增 `regenerate_main_audio.py` 等工具脚本，TTS / 文本处理优化
- **v1.5** — 时点内容格式优化、时间戳修复
- **v1.4** — 统一 1.05× 倍速 + 2.6× 音量
- **v1.3** — 自动化播客生成全流程
- **v1.2** — 2-speaker 简化方案、TTS 分段优化
- **v1.0** — 基础功能

## ⚠️ 说明

本仓库依赖第三方付费 API（DashScope / Gemini / MiniMax），请自行申请 Key 并注意调用费用。仅供个人学习与研究使用。

## 📄 License

个人使用与学习。商用请先与作者联系。
