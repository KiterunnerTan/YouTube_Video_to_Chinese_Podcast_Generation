"""
重新生成主音频（仅替换音色配置）

用途：当需要更换 speaker 音色时，仅重新生成主音频 TTS，
复用现有的开场白、概要、音乐，合并最终播客。
"""

import json
import subprocess
import time
import shutil
from pathlib import Path
from config import Config

Config.setup_proxy()

# ============================================================================
# 配置
# ============================================================================
PODCAST_NAME = "Head of Claude Code： What happens after coding is solved _ Boris Cherny"
ASR_HASH = "d70bf95ff5cafbd3"

# 新的音色配置
NEW_VOICE_MAPPING = {
    "speaker_0": "Chinese (Mandarin)_Crisp_Girl",
    "speaker_1": "male-qn-jingying"
}

print("=" * 80)
print("重新生成主音频（替换音色配置）")
print("=" * 80)
print(f"播客: {PODCAST_NAME}")
print(f"新音色配置: {NEW_VOICE_MAPPING}")

# ============================================================================
# 步骤1: 准备音频片段目录（支持断点续传）
# ============================================================================
print("\n步骤1: 准备音频片段目录...")
audio_dir = Path(f"output/audio_segments/final_{ASR_HASH}")
audio_dir.mkdir(parents=True, exist_ok=True)

# 检查已有的音频片段
existing_segments = list(audio_dir.glob("segment_*.mp3"))
print(f"✓ 已有 {len(existing_segments)} 个音频片段（将跳过）")

# 删除旧的主音频文件（需要重新合并）
main_audio_raw = Path(f"output/temp/main_audio_raw_{ASR_HASH}.mp3")
main_audio_final = Path(f"output/temp/main_audio_final_{ASR_HASH}.mp3")
for f in [main_audio_raw, main_audio_final]:
    if f.exists():
        f.unlink()
        print(f"✓ 已删除: {f}")

# ============================================================================
# 步骤2: 加载优化后的翻译
# ============================================================================
print("\n步骤2: 加载翻译...")
optimized_file = Path("output/translations/asr_optimized.json")
with open(optimized_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
translations = data.get('translations', [])
print(f"✓ 加载了 {len(translations)} 个翻译段落")

# ============================================================================
# 步骤3: 初始化 TTS 生成器（使用新音色）
# ============================================================================
print("\n步骤3: 初始化 TTS 生成器...")
from utils.tts_generator_v1_4 import GeminiTTSGeneratorV14, VoiceManager
from utils.tts_segment_optimizer import parse_optimized_segments

voice_manager = VoiceManager(voice_config=NEW_VOICE_MAPPING)
tts_generator = GeminiTTSGeneratorV14(
    api_key=Config.MINIMAX_API_KEY,
    group_id=Config.MINIMAX_GROUP_ID,
    model_name="speech-2.8-hd",
    voice_manager=voice_manager,
    enable_cache=True
)
print(f"✓ TTS 生成器就绪")

# ============================================================================
# 步骤4: 生成主音频 TTS
# ============================================================================
print("\n步骤4: 生成主音频 TTS...")
print("=" * 80)

audio_files = []
for i, translation in enumerate(translations):
    segment_id = translation.get('segment_id', i)
    text = translation.get('optimized_text', translation.get('translated_text', ''))

    # 解析优化后的文本
    if '[SEG_' in text or '[SKIP]' in text:
        segments_parsed, skipped = parse_optimized_segments(text)
        if skipped:
            print(f"  [Segment {segment_id}] 跳过 {len(skipped)} 个简单回应")
        combined_text = ""
        for seg in segments_parsed:
            combined_text += f"{seg['speaker']}: {seg['content']}\n"
        text = combined_text.strip()

    if not text.strip():
        print(f"[Segment {segment_id}] ⏩ 跳过（空内容）")
        continue

    audio_file = audio_dir / f"segment_{segment_id:04d}.mp3"

    # 断点续传：跳过已存在的文件
    if audio_file.exists() and audio_file.stat().st_size > 1000:
        print(f"[Segment {segment_id}] ⏩ 跳过（已存在）")
        duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                       '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_file)]
        try:
            duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
            audio_files.append({'file': str(audio_file), 'duration': duration})
            print(f"  ✓ {duration:.1f}秒")
            continue
        except:
            print(f"  ⚠️ 文件可能损坏，重新生成")
            audio_file.unlink()

    print(f"[Segment {segment_id}] 生成音频...")
    tts_generator.generate_audio(text=text, output_path=audio_file)

    # 限速
    if i < len(translations) - 1:
        time.sleep(3)

    # 获取时长
    duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_file)]
    duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())

    audio_files.append({'file': str(audio_file), 'duration': duration})
    print(f"  ✓ {duration:.1f}秒")

print(f"\n✓ 共生成 {len(audio_files)} 个音频片段")

# ============================================================================
# 步骤5: 合并主音频
# ============================================================================
print("\n步骤5: 合并主音频...")

def concat_audio_files(input_files, output_file):
    """使用 FFmpeg filter_complex 合并音频"""
    filter_parts = []
    for i in range(len(input_files)):
        filter_parts.append(f"[{i}:a]")
    filter_complex = "".join(filter_parts) + f"concat=n={len(input_files)}:v=0:a=1[out]"

    cmd = ['ffmpeg']
    for f in input_files:
        cmd.extend(['-i', f])
    cmd.extend([
        '-filter_complex', filter_complex,
        '-map', '[out]',
        '-ar', '24000', '-ac', '1', '-b:a', '128k',
        '-y', output_file
    ])
    return subprocess.run(cmd, capture_output=True, text=True)

input_files = [af['file'] for af in audio_files]
result = concat_audio_files(input_files, str(main_audio_raw))
if result.returncode != 0:
    print(f"❌ 合并失败: {result.stderr}")
    exit(1)

# 应用1.05倍速 + 2.6倍音量
cmd = [
    'ffmpeg', '-i', str(main_audio_raw),
    '-filter:a', 'atempo=1.05,volume=2.6',
    '-ar', '24000', '-ac', '1', '-b:a', '128k',
    '-y', str(main_audio_final)
]
subprocess.run(cmd, capture_output=True, check=True)
print("✓ 主音频生成完成 (1.05倍速 + 2.6倍音量)")

# ============================================================================
# 步骤6: 合并完整播客（复用开场白、概要、音乐）
# ============================================================================
print("\n步骤6: 合并完整播客...")

music_1_final = Path("output/temp/music_1_final.mp3")
music_2_final = Path("output/temp/music_2_final.mp3")
prologue_final = Path("output/temp/prologue_final.mp3")
summary_final = Path(f"output/temp/summary_final_{ASR_HASH}.mp3")

# 验证文件存在
for f in [music_1_final, music_2_final, prologue_final, summary_final]:
    if not f.exists():
        print(f"❌ 缺少文件: {f}")
        exit(1)
    print(f"✓ 复用: {f.name}")

final_input_files = [
    str(music_1_final.absolute()),
    str(prologue_final.absolute()),
    str(music_2_final.absolute()),
    str(summary_final.absolute()),
    str(music_2_final.absolute()),
    str(main_audio_final.absolute()),
    str(music_1_final.absolute()),
]

podcast_final_dir = Path("output/podcast_final")
podcast_final_dir.mkdir(parents=True, exist_ok=True)
final_output = podcast_final_dir / f"{PODCAST_NAME}.mp3"

# 备份旧文件
if final_output.exists():
    backup = final_output.with_suffix('.mp3.bak')
    shutil.copy(final_output, backup)
    print(f"✓ 已备份旧文件: {backup.name}")

result = concat_audio_files(final_input_files, str(final_output))
if result.returncode != 0:
    print(f"❌ 最终合并失败: {result.stderr}")
    exit(1)

# 获取最终时长
duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
               '-of', 'default=noprint_wrappers=1:nokey=1', str(final_output)]
final_duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())

print("\n" + "=" * 80)
print("✅ 完成！")
print("=" * 80)
print(f"总时长: {final_duration/60:.1f}分钟")
print(f"文件: {final_output}")
print(f"\n音色配置:")
for k, v in NEW_VOICE_MAPPING.items():
    print(f"  {k}: {v}")
