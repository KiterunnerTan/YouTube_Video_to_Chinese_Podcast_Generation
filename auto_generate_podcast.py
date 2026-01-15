"""完整播客自动生成流程（包含所有优化）

使用方法：
python auto_generate_podcast.py
"""
from pathlib import Path
from config import Config
import subprocess
import json
import tempfile
from utils.podcast_name_parser import PodcastNameParser
from utils.podcast_manager import PodcastManager
import glob

# 设置配置
Config.setup_proxy()
Config.validate()

# 检查必需的外部依赖
def check_dependencies():
    """检查必需的外部工具和文件"""
    import shutil

    # 检查 ffmpeg
    if not shutil.which('ffmpeg'):
        print("❌ 错误：未找到 ffmpeg")
        print("请安装 ffmpeg: brew install ffmpeg (macOS) 或访问 https://ffmpeg.org/")
        exit(1)

    # 检查必需的文件
    required_files = [
        ("output/prologue_voice_clone.json", "开场白音色配置文件"),
        ("music/music_1.m4a", "片头音乐文件"),
        ("music/music_2.m4a", "过渡音乐文件"),
    ]

    missing_files = []
    for file_path, description in required_files:
        if not Path(file_path).exists():
            missing_files.append(f"  - {file_path} ({description})")

    if missing_files:
        print("❌ 错误：缺少必需文件：")
        for f in missing_files:
            print(f)
        print("\n请确保这些文件存在后再运行。")
        exit(1)

check_dependencies()

# 解析节目名
try:
    PODCAST_NAME = PodcastNameParser.parse_podcast_name()
    print(f"📻 当前节目: {PODCAST_NAME}")
except Exception as e:
    print(f"❌ 解析节目名失败: {e}")
    print("使用默认名称: 未命名播客")
    PODCAST_NAME = "未命名播客"

# 智能查找ASR文件
def find_latest_asr_file(podcast_name=None):
    """
    查找匹配的ASR文件，优先从新的播客目录查找

    Args:
        podcast_name: 目标播客名称（用于匹配验证）

    Returns:
        匹配的ASR文件路径
    """
    from datetime import datetime
    import re

    print("\n" + "=" * 80)
    print("🔍 查找匹配的ASR文件")
    print("=" * 80)
    if podcast_name:
        print(f"目标播客: {podcast_name}")

    # 从 start_prompt.md 获取 YouTube URL（用于匹配验证）
    youtube_url = None
    try:
        with open(Path("start_prompt.md"), 'r', encoding='utf-8') as f:
            content = f.read()
        url_patterns = [
            r'YouTube URL[:：]\s*(https?://[^\s\n]+)',
            r'视频链接[:：]\s*(https?://[^\s\n]+)',
            r'URL[:：]\s*(https?://[^\s\n]+)',
        ]
        for pattern in url_patterns:
            match = re.search(pattern, content)
            if match:
                youtube_url = match.group(1).strip()
                break
        if youtube_url:
            print(f"目标URL: {youtube_url}")
    except Exception:
        pass

    print()

    # 方案1: 尝试从新的播客目录查找（推荐）
    if youtube_url:
        manager = PodcastManager()
        podcast_id = manager.find_podcast_by_url(youtube_url)

        if podcast_id:
            asr_path = manager.get_asr_path(podcast_id)
            if asr_path.exists():
                metadata = manager.load_metadata(podcast_id)
                print("✅ 找到新格式的ASR文件（播客目录）")
                print(f"  ID: {podcast_id}")
                print(f"  文件: {asr_path}")
                print(f"  播客名: {metadata.get('podcast_name', '未知')}")
                print(f"  URL: {metadata.get('youtube_url', '未知')}")
                print()
                return asr_path

    # 方案2: 从旧的 asr_results 目录查找（兼容旧版本）
    asr_dir = Path("output/asr_results")
    if not asr_dir.exists():
        print("❌ 未找到ASR文件")
        print("请先运行: python generate.py 下载视频并转录")
        raise FileNotFoundError("未找到ASR文件")

    print("⚠️  使用旧格式的ASR目录查找...")

    # 查找所有ASR文件（排除空文件）
    processed_files = []
    for pattern in ["*processed*.json", "qwen_asr_*.json"]:
        for file_path in glob.glob(str(asr_dir / pattern)):
            file_size = Path(file_path).stat().st_size
            if file_size > 1000:  # 排除小于1KB的文件
                processed_files.append(Path(file_path))

    if not processed_files:
        raise FileNotFoundError("未找到任何ASR文件，请先运行ASR转录流程")

    print(f"找到 {len(processed_files)} 个ASR文件\n")

    # 首先尝试精确匹配（URL + 播客名）
    if youtube_url or podcast_name:
        for asr_file in processed_files:
            try:
                with open(asr_file, 'r', encoding='utf-8') as f:
                    asr_data = json.load(f)

                metadata = asr_data.get('metadata', {})

                # 优先URL匹配
                if youtube_url and metadata.get('youtube_url') == youtube_url:
                    print("✅ 找到精确匹配的ASR文件（URL匹配）")
                    print(f"  文件: {asr_file.name}")
                    print(f"  播客名: {metadata.get('podcast_name', '未知')}")
                    print(f"  URL: {metadata.get('youtube_url', '未知')}")
                    print(f"  创建时间: {metadata.get('created_at', '未知')}")
                    print()
                    return asr_file

                # 次要：播客名匹配
                if podcast_name and metadata.get('podcast_name') == podcast_name:
                    print("✅ 找到匹配的ASR文件（播客名匹配）")
                    print(f"  文件: {asr_file.name}")
                    print(f"  播客名: {metadata.get('podcast_name', '未知')}")
                    print(f"  URL: {metadata.get('youtube_url', '未知')}")
                    print(f"  创建时间: {metadata.get('created_at', '未知')}")
                    if youtube_url and metadata.get('youtube_url') != youtube_url:
                        print(f"  ⚠️  警告：URL不匹配！")
                    print()
                    return asr_file

            except Exception:
                # 旧格式文件没有metadata，继续
                continue

    # 如果没有找到精确匹配，使用最新的文件并警告
    processed_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    latest_file = processed_files[0]
    mod_time = datetime.fromtimestamp(latest_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    print("⚠️  未找到精确匹配的ASR文件！")
    print("⚠️  使用最新的ASR文件（可能不是正确的播客）")
    print(f"  文件: {latest_file.name}")
    print(f"  修改时间: {mod_time}")

    # 尝试读取metadata显示信息
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            asr_data = json.load(f)
        metadata = asr_data.get('metadata', {})
        if metadata:
            print(f"  播客名: {metadata.get('podcast_name', '未知')}")
            print(f"  URL: {metadata.get('youtube_url', '未知')}")
    except Exception:
        pass

    print()
    print("⚠️  请确认这是正确的播客！如果不是，请运行 python generate.py 重新生成")
    print()

    return latest_file

# 查找ASR文件
try:
    ASR_FILE = find_latest_asr_file(podcast_name=PODCAST_NAME)
except FileNotFoundError as e:
    print(f"\n❌ {e}")
    print("请先运行ASR转录流程生成文字稿")
    exit(1)

print("=" * 80)
print("🎙️ 完整播客自动生成流程")
print("=" * 80)

# ============================================================================
# 步骤1: 生成开场白（增强版，2.2倍音量）
# ============================================================================
print("\n步骤1: 生成开场白...")
print("=" * 80)

from utils.voice_clone_manager import VoiceCloneManager

PROLOGUE_TEXT = """大家好！欢迎收听……《西经东译》。

如果你和我一样，厌倦了在同质化的AI二手信息中打转，渴望第一时间了解彼岸的优质内容，但又苦于语言的壁垒。那么……这个播客，就是为你准备的！

我是主播杰瑞，一位深耕AI领域的产品经理。很荣幸，能为你搭建这座跨越语言的桥梁，带你零距离追踪全球一手的顶尖播客。

欢迎关注同名公众号，获取更多内容！"""

clone_info_file = Path("output/prologue_voice_clone.json")
voice_clone_manager = VoiceCloneManager(
    api_key=Config.MINIMAX_API_KEY,
    group_id=Config.MINIMAX_GROUP_ID
)

clone_info = voice_clone_manager.load_clone_info(clone_info_file)
if not clone_info:
    print("❌ 未找到克隆音色，请先运行完整流程创建")
    exit(1)

voice_id = clone_info['voice_id']
temp_prologue = Path("output/temp/prologue_raw.mp3")
temp_prologue.parent.mkdir(parents=True, exist_ok=True)

# 生成原始开场白
voice_clone_manager.generate_audio_with_cloned_voice(
    text=PROLOGUE_TEXT,
    voice_id=voice_id,
    output_path=temp_prologue,
    speed=1.0
)

# 应用1.1倍速 + 2.2倍音量
prologue_final = Path("output/temp/prologue_final.mp3")
cmd = [
    'ffmpeg', '-i', str(temp_prologue),
    '-filter:a', 'atempo=1.1,volume=2.6',
    '-ar', '24000', '-ac', '1', '-b:a', '128k',
    '-y', str(prologue_final)
]
subprocess.run(cmd, capture_output=True, check=True)
print("✓ 开场白生成完成 (1.1倍速 + 2.2倍音量)")

# ============================================================================
# 步骤2: 生成节目概要（增强情绪，2.2倍音量）
# ============================================================================
print("\n步骤2: 生成节目概要...")
print("=" * 80)

from utils.episode_summary_generator import EpisodeSummaryGenerator

summary_generator = EpisodeSummaryGenerator(Config.GEMINI_API_KEY)

summary_text = summary_generator.generate_from_files(
    start_prompt_file=Path("start_prompt.md"),
    asr_file=ASR_FILE,
    target_length=120
)

if not summary_text:
    print("⚠️  概要生成失败，使用默认概要")
    summary_text = """本期播客将深入探讨人工智能领域的最新趋势和突破性进展。我们的嘉宾将分享他们在AI行业的独到见解……从技术创新到商业应用，从挑战到机遇！让我们一起来听听这场精彩的对话吧。"""

# 保存概要文本
summary_file = Path("output/episode_summary.txt")
with open(summary_file, 'w', encoding='utf-8') as f:
    f.write(summary_text)

# 生成概要音频
temp_summary = Path("output/temp/summary_raw.mp3")
voice_clone_manager.generate_audio_with_cloned_voice(
    text=summary_text,
    voice_id=voice_id,
    output_path=temp_summary,
    speed=1.0
)

# 应用1.1倍速 + 2.2倍音量
summary_final = Path("output/temp/summary_final.mp3")
cmd = [
    'ffmpeg', '-i', str(temp_summary),
    '-filter:a', 'atempo=1.1,volume=2.6',
    '-ar', '24000', '-ac', '1', '-b:a', '128k',
    '-y', str(summary_final)
]
subprocess.run(cmd, capture_output=True, check=True)
print("✓ 节目概要生成完成 (1.1倍速 + 2.2倍音量)")

# ============================================================================
# 步骤3: 处理ASR结果，生成formatted_text（关键步骤！）
# ============================================================================
print("\n步骤3: 处理ASR结果...")
print("=" * 80)

from utils.text_processor import TextProcessor

# 读取原始ASR文件
with open(ASR_FILE, 'r', encoding='utf-8') as f:
    asr_data = json.load(f)

# 检查是否已经有formatted_text（处理过的文件）
segments = asr_data.get('segments', [])
if segments and 'formatted_text' not in segments[0]:
    # 需要处理：提取文本并生成formatted_text
    print("⚠️  ASR文件缺少formatted_text，正在处理...")
    processor = TextProcessor(segment_duration_minutes=3)  # 3分钟段落（与ASR分段一致）
    processed_result = processor.process_asr_result(asr_data)
    segments = processed_result.get('segments', [])

    # 保存处理后的ASR文件（带formatted_text）
    processed_asr_file = Path(f"output/asr_results/{ASR_FILE.stem}_processed.json")
    processor.save_processed_result(processed_result, processed_asr_file)
    print(f"✓ 已生成formatted_text，保存到: {processed_asr_file.name}")
else:
    print("✓ ASR文件已包含formatted_text")

print(f"✓ ASR段落数: {len(segments)}")

# ============================================================================
# 步骤4: 翻译并生成主音频（使用增强prompt）
# ============================================================================
print("\n步骤4: 翻译并生成主音频...")
print("=" * 80)

from utils.translator_v1_4 import GeminiTranslatorV14
from utils.tts_generator_v1_4 import GeminiTTSGeneratorV14, VoiceManager
from utils.voice_config_parser import VoiceConfigParser

# 翻译（使用缓存如果存在，并验证hash）
# 根据ASR文件名生成对应的翻译缓存文件名
asr_basename = ASR_FILE.stem  # 获取文件名（不含扩展名）
translations_output = Path(f"output/translations/{asr_basename}_translations_enhanced.json")

# 计算当前ASR文件的hash
import hashlib
with open(ASR_FILE, 'rb') as f:
    current_asr_hash = hashlib.sha256(f.read()).hexdigest()[:16]

# 检查缓存翻译文件是否存在且有效
use_cache = False
if translations_output.exists():
    try:
        with open(translations_output, 'r', encoding='utf-8') as f:
            translations_data = json.load(f)

        # 验证hash（兼容旧格式：没有metadata的情况）
        cached_hash = translations_data.get('metadata', {}).get('asr_hash')
        if cached_hash:
            if cached_hash == current_asr_hash:
                print(f"✓ 使用缓存的翻译（hash验证通过: {current_asr_hash}）")
                use_cache = True
            else:
                print(f"⚠️  缓存翻译的ASR源不匹配！")
                print(f"  当前ASR hash: {current_asr_hash}")
                print(f"  缓存ASR hash: {cached_hash}")
                print(f"  删除旧翻译并重新生成...")
                translations_output.unlink()
        else:
            # 旧格式没有hash，为安全起见重新生成
            print(f"⚠️  缓存翻译没有hash验证信息，删除并重新生成...")
            translations_output.unlink()
    except Exception as e:
        print(f"⚠️  读取缓存翻译失败: {e}")
        translations_output.unlink() if translations_output.exists() else None

if use_cache:
    translations = translations_data.get('translations', [])
else:
    print("开始翻译...")
    translator = GeminiTranslatorV14(
        api_key=Config.GEMINI_API_KEY,
        model_name="gemini-2.5-pro"
    )
    translations = translator.translate_all_segments(segments, delay_between_calls=4.0)
    translator.save_translations(
        translations,
        translations_output,
        asr_file_path=ASR_FILE,
        podcast_name=PODCAST_NAME
    )

# 生成TTS
voice_config = VoiceConfigParser.parse_voice_config()
voice_manager = VoiceManager(voice_config=voice_config)
tts_generator = GeminiTTSGeneratorV14(
    api_key=Config.MINIMAX_API_KEY,
    group_id=Config.MINIMAX_GROUP_ID,
    model_name="speech-2.6-hd",
    voice_manager=voice_manager,
    enable_cache=True
)

# 使用ASR hash创建独立的音频段目录（避免混用不同播客的音频）
audio_dir = Path(f"output/audio_segments/final_{current_asr_hash}")

# 关键修复：检查音频缓存是否比翻译文件更旧，如果是则删除
if audio_dir.exists():
    audio_dir_mtime = audio_dir.stat().st_mtime
    translation_file_mtime = translations_output.stat().st_mtime if translations_output.exists() else 0

    if audio_dir_mtime < translation_file_mtime:
        print(f"⚠️  音频缓存早于翻译文件，删除旧缓存...")
        import shutil
        shutil.rmtree(audio_dir)
        print(f"✓ 已删除旧音频缓存，将重新生成")

audio_dir.mkdir(parents=True, exist_ok=True)
print(f"✓ 音频段目录: {audio_dir.name}")

audio_files = []
for i, translation in enumerate(translations):
    segment_id = translation['segment_id']
    text = translation['translated_text']
    audio_file = audio_dir / f"segment_{segment_id:04d}.mp3"

    # 断点续传：检查文件是否已存在
    if audio_file.exists() and audio_file.stat().st_size > 1000:
        print(f"[Segment {segment_id}] ⏩ 跳过（已存在）")
        # 获取已有文件的时长
        duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                       '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_file)]
        try:
            duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
            audio_files.append({'file': str(audio_file), 'duration': duration})
            print(f"  ✓ {duration:.1f}秒")
            continue
        except:
            # 如果文件损坏，删除后重新生成
            print(f"  ⚠️  文件可能损坏，重新生成")
            audio_file.unlink()

    print(f"[Segment {segment_id}] 生成音频...")
    tts_generator.generate_audio(text=text, output_path=audio_file)

    duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_file)]
    duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())

    audio_files.append({'file': str(audio_file), 'duration': duration})
    print(f"  ✓ {duration:.1f}秒")

# 合并主音频
main_audio_temp = Path("output/temp/main_audio_raw.mp3")
with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
    for af in audio_files:
        # 使用绝对路径以确保ffmpeg能找到文件
        abs_path = Path(af['file']).absolute()
        f.write(f"file '{abs_path}'\n")
    concat_list = f.name

# 不使用 -c copy，而是重新编码以确保兼容性
cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list,
       '-ar', '24000', '-ac', '1', '-b:a', '128k', '-y', str(main_audio_temp)]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"❌ FFmpeg concat 失败:")
    print(f"错误信息: {result.stderr}")
    raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
Path(concat_list).unlink()

# 应用1.1倍速 + 2.2倍音量
main_audio_final = Path("output/temp/main_audio_final.mp3")
cmd = [
    'ffmpeg', '-i', str(main_audio_temp),
    '-filter:a', 'atempo=1.1,volume=2.6',
    '-ar', '24000', '-ac', '1', '-b:a', '128k',
    '-y', str(main_audio_final)
]
subprocess.run(cmd, capture_output=True, check=True)
print("✓ 主音频生成完成 (1.1倍速 + 2.2倍音量)")

# ============================================================================
# 步骤5: 准备音乐（转换格式、降低音量、添加渐出效果）
# ============================================================================
print("\n步骤5: 准备音乐...")
print("=" * 80)

music_1_m4a = Path("music/music_1.m4a")
music_2_m4a = Path("music/music_2.m4a")

music_1_final = Path("output/temp/music_1_final.mp3")
music_2_final = Path("output/temp/music_2_final.mp3")

# 获取音乐时长
duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', str(music_1_m4a)]
music_1_duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())

duration_cmd_2 = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                  '-of', 'default=noprint_wrappers=1:nokey=1', str(music_2_m4a)]
music_2_duration = float(subprocess.run(duration_cmd_2, capture_output=True, text=True).stdout.strip())

# 渐出时长（最后2秒）
fadeout_duration = 2.0
music_1_fadeout_start = max(0, music_1_duration - fadeout_duration)
music_2_fadeout_start = max(0, music_2_duration - fadeout_duration)

# 转换music_1：降低音量到0.4倍 + 最后2秒渐出
cmd = [
    'ffmpeg', '-i', str(music_1_m4a),
    '-filter:a', f'volume=0.4,afade=t=out:st={music_1_fadeout_start}:d={fadeout_duration}',
    '-ar', '24000', '-ac', '1', '-b:a', '128k', '-y', str(music_1_final)
]
subprocess.run(cmd, capture_output=True, check=True)

# 转换music_2：降低音量到0.4倍 + 最后2秒渐出
cmd = [
    'ffmpeg', '-i', str(music_2_m4a),
    '-filter:a', f'volume=0.4,afade=t=out:st={music_2_fadeout_start}:d={fadeout_duration}',
    '-ar', '24000', '-ac', '1', '-b:a', '128k', '-y', str(music_2_final)
]
subprocess.run(cmd, capture_output=True, check=True)

print(f"✓ 音乐文件准备完成 (音量0.4倍 + {fadeout_duration}秒渐出)")

# ============================================================================
# 步骤6: 合并完整播客
# ============================================================================
print("\n步骤6: 合并完整播客...")
print("=" * 80)

with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
    f.write(f"file '{music_1_final.absolute()}'\n")      # 片头音乐
    f.write(f"file '{prologue_final.absolute()}'\n")     # 开场白
    f.write(f"file '{music_2_final.absolute()}'\n")      # 过渡音乐
    f.write(f"file '{summary_final.absolute()}'\n")      # 节目概要
    f.write(f"file '{music_2_final.absolute()}'\n")      # 过渡音乐
    f.write(f"file '{main_audio_final.absolute()}'\n")   # 主音频
    f.write(f"file '{music_1_final.absolute()}'\n")      # 片尾音乐
    concat_list = f.name

# 创建输出目录并设置最终输出路径
podcast_final_dir = Path("output/podcast_final")
podcast_final_dir.mkdir(parents=True, exist_ok=True)
final_output = podcast_final_dir / f"{PODCAST_NAME}.mp3"

try:
    # 不使用 -c copy，而是重新编码以确保兼容性
    cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list,
           '-ar', '24000', '-ac', '1', '-b:a', '128k', '-y', str(final_output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFmpeg 最终合并失败:")
        print(f"错误信息: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

    duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', str(final_output)]
    final_duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())

    print("✓ 播客合并完成")
    print(f"  总时长: {final_duration/60:.1f}分钟")
    print(f"  文件: {final_output}")

finally:
    Path(concat_list).unlink()

# ============================================================================
# 步骤7: 生成播客介绍文案
# ============================================================================
print("\n步骤7: 生成播客介绍文案...")
print("=" * 80)

from utils.podcast_description_generator import PodcastDescriptionGenerator
from utils.podcast_name_parser import PodcastNameParser

desc_generator = PodcastDescriptionGenerator(Config.GEMINI_API_KEY)

# 从 start_prompt.md 提取 YouTube URL
try:
    import re
    with open(Path("start_prompt.md"), 'r', encoding='utf-8') as f:
        content = f.read()
    url_patterns = [
        r'YouTube URL[:：]\s*(https?://[^\s\n]+)',
        r'视频链接[:：]\s*(https?://[^\s\n]+)',
        r'URL[:：]\s*(https?://[^\s\n]+)',
    ]
    youtube_url = None
    for pattern in url_patterns:
        match = re.search(pattern, content)
        if match:
            youtube_url = match.group(1).strip()
            break
    if not youtube_url:
        youtube_url = "www.youtube.com"  # 默认值
except Exception:
    youtube_url = "www.youtube.com"  # 出错时使用默认值

description = desc_generator.generate_from_files(
    start_prompt_file=Path("start_prompt.md"),
    asr_file=ASR_FILE,
    video_url=youtube_url
)

if description:
    # 创建节目描述文案输出目录
    description_dir = Path("output/description")
    description_dir.mkdir(parents=True, exist_ok=True)
    desc_file = description_dir / f"{PODCAST_NAME}.txt"

    with open(desc_file, 'w', encoding='utf-8') as f:
        f.write(description)
    print(f"✓ 文案已保存: {desc_file}")

# ============================================================================
# 完成
# ============================================================================
print("\n" + "=" * 80)
print("✅ 完整播客生成成功！")
print("=" * 80)
print(f"\n📻 节目名称: {PODCAST_NAME}")
print(f"\n📁 输出文件:")
print(f"  - 播客音频: {final_output}")
print(f"  - 节目介绍: {desc_file if description else '未生成'}")
print(f"\n🎵 播客结构:")
print(f"  music_1(渐出) → 开场白 → music_2(渐出) → 概要 → music_2(渐出) → 主音频 → music_1(渐出)")
print(f"\n🔊 音量设置:")
print(f"  - 开场白/概要/主音频: 2.6倍音量")
print(f"  - 音乐: 0.4倍音量")
print(f"\n⚡ 倍速设置:")
print(f"  - 所有音频: 1.1倍速（音乐除外）")
print(f"\n🎶 音乐效果:")
print(f"  - 所有音乐: 最后2秒渐出效果")
print("\n" + "=" * 80)
