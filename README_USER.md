# 西经东译播客自动生成器

一键将英文视频播客转译成专业的中文播客，包含双语主持人对话、音乐过渡和专业文案。

## 快速开始

### 1. 准备工作

确保已安装依赖：

```bash
# 安装Python依赖
pip install -r requirements.txt

# 确保系统已安装ffmpeg
brew install ffmpeg  # macOS
# 或
apt-get install ffmpeg  # Linux
```

### 2. 配置API密钥

在 `.env` 文件中配置以下API密钥：

```env
# 阿里云DashScope API（用于ASR语音识别）
DASHSCOPE_API_KEY=your_dashscope_api_key

# Google Gemini API（用于翻译）
GEMINI_API_KEY=your_gemini_api_key

# MiniMax API（用于TTS语音合成）
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_GROUP_ID=your_group_id

# 代理设置（可选）
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
```

### 3. 编辑配置文件

编辑 `start_prompt.md` 文件，填入本期播客信息：

```markdown
播客名字是{OpenAI CEO深度对话：OpenAI如何制胜、ChatGPT的未来、AI发展逻辑}，嘉宾是{OpenAI首席执行官Sam Altman}。

当前要转译的cookie文件目录地址：{/path/to/cookie.txt}

音色配置: speaker_0:{Chinese (Mandarin)_Crisp_Girl}, speaker_1:{Deep_Voice_Man}

基于以上信息，给我自动生成完整的播客节目！
```

### 4. 一键生成播客

```bash
python generate.py
```

就这么简单！程序会自动完成：
1. 语音识别（ASR）
2. 中文翻译（增强prompt，自然+情绪+节奏）
3. 语音合成（双语主持人对话）
4. 音频合并（音乐+开场白+概要+主音频）
5. 文案生成（专业播客介绍）

### 5. 获取输出

生成完成后，在 `output/` 目录下找到：

- **播客音频**：`podcast_final.mp3`
- **节目介绍文案**：`podcast_description.txt`

## 播客结构

```
片头音乐（渐出）
↓
开场白（克隆音色，2.6倍音量，1.1倍速）
↓
过渡音乐（渐出）
↓
节目概要（增强情绪，2.6倍音量，1.1倍速）
↓
过渡音乐（渐出）
↓
主音频（双语对话，2.6倍音量，1.1倍速）
↓
片尾音乐（渐出）
```

## 音频参数

| 部分 | 音量 | 倍速 | 特效 |
|------|------|------|------|
| 开场白 | 2.6倍 | 1.1倍 | - |
| 节目概要 | 2.6倍 | 1.1倍 | 增强情绪 |
| 主音频 | 2.6倍 | 1.1倍 | 自然节奏 |
| 音乐 | 0.4倍 | 1.0倍 | 2秒渐出 |

## 音色配置

可用的中文音色（示例）：

**女声**：
- `Chinese (Mandarin)_Crisp_Girl` - 清脆女声
- `Chinese (Mandarin)_Warm_Bestie` - 温暖好友
- `Chinese (Mandarin)_News_Anchor` - 新闻主播

**男声**：
- `Deep_Voice_Man` - 深沉男声
- `Chinese (Mandarin)_Reliable_Executive` - 可靠管理者
- `Chinese (Mandarin)_Gentleman` - 绅士

在 `start_prompt.md` 中修改音色配置：
```
音色配置: speaker_0:{女声ID}, speaker_1:{男声ID}
```

## 优化特性

### 翻译优化（v1.4）
- ✅ 自然口语化表达
- ✅ 情绪起伏（惊讶、质疑、兴奋）
- ✅ 节奏变化（快慢对比、停顿控制）
- ✅ 重读表达（自然强调）

### TTS优化
- ✅ 双语主持人对话
- ✅ 情绪自动推断
- ✅ 音量和倍速优化
- ✅ 音乐渐出效果

### 文案生成
- ✅ 专业播客介绍
- ✅ Key Topics提炼
- ✅ 适合分发的格式

## 常见问题

### Q: 如何更换音色？
A: 编辑 `start_prompt.md`，修改 `音色配置` 行即可。

### Q: 如何调整音量？
A: 编辑 `auto_generate_podcast.py`，搜索 `volume=2.6` 修改倍数。

### Q: 生成失败怎么办？
A: 检查：
1. API密钥是否正确
2. 网络代理是否可用
3. Cookie文件路径是否正确
4. 查看详细错误日志

### Q: 如何跳过已完成的步骤？
A: 程序会自动检测缓存：
- 翻译结果缓存在 `output/translations/`
- TTS音频缓存在 `output/audio_segments/`

## 项目结构

```
.
├── generate.py                      # 主入口（运行这个！）
├── auto_generate_podcast.py         # 完整自动化流程
├── start_prompt.md                  # 配置文件（编辑这个！）
├── config.py                        # API配置
├── utils/                           # 核心模块
│   ├── translator_v1_4.py          # 翻译引擎
│   ├── tts_generator_v1_4.py       # TTS引擎
│   ├── episode_summary_generator.py # 概要生成
│   ├── podcast_description_generator.py # 文案生成
│   └── voice_config_parser.py      # 音色配置解析
├── music/                           # 音乐素材
│   ├── music_1.m4a                 # 片头/片尾音乐
│   └── music_2.m4a                 # 过渡音乐
├── output/                          # 输出目录
│   ├── podcast_final.mp3           # 最终播客
│   └── podcast_description.txt     # 节目介绍
└── README_USER.md                   # 本文件
```

## 版本历史

- **v1.4** - 增强版prompt，音乐渐出，2.6倍音量（当前版本）
- **v1.3** - 新音色，1.1倍速，专业文案生成
- **v1.2** - 情绪和节奏优化
- **v1.1** - 翻译prompt优化
- **v1.0** - 基础功能完成

## 技术栈

- **ASR**: 阿里云DashScope Qwen
- **翻译**: Google Gemini 2.5 Flash
- **TTS**: MiniMax Speech 2.6 HD
- **音频处理**: FFmpeg
- **开发语言**: Python 3.14

## 许可证

本项目仅供个人学习和使用。

## 联系方式

如有问题，请关注微信公众号"西经东译"获取AI最新资讯。

---

**祝您制作出精彩的播客！** 🎙️
