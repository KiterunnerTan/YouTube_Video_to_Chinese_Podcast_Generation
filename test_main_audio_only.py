#!/usr/bin/env python3
"""只生成主音频部分，用于测试验证"""
from pathlib import Path
from config import Config
import json
import subprocess
import tempfile

Config.setup_proxy()
Config.validate()

# 读取ASR文件
ASR_FILE = Path("output/asr_results/qwen_asr_20260102_153544.json")
print(f"✓ ASR文件: {ASR_FILE.name}")

# 处理ASR
from utils.text_processor import TextProcessor

with open(ASR_FILE, 'r', encoding='utf-8') as f:
    asr_data = json.load(f)

segments = asr_data.get('segments', [])
if segments and 'formatted_text' not in segments[0]:
    print("⚠️  处理ASR文件...")
    processor = TextProcessor(segment_duration_minutes=3)
    processed_result = processor.process_asr_result(asr_data)
    segments = processed_result.get('segments', [])
else:
    print("✓ ASR文件已包含formatted_text")

# 读取翻译文件
translations_file = Path("output/translations/qwen_asr_20260102_153544_translations_enhanced.json")
with open(translations_file, 'r', encoding='utf-8') as f:
    translations_data = json.load(f)

translations = translations_data.get('translations', [])
print(f"✓ 翻译段落数: {len(translations)}")
print(f"✓ 第一段原文开头: {translations[0]['original_text'][:50]}...")
print(f"✓ 第一段译文开头: {translations[0]['translated_text'][:50]}...")

# 计算hash
import hashlib
with open(ASR_FILE, 'rb') as f:
    current_asr_hash = hashlib.sha256(f.read()).hexdigest()[:16]

# 生成TTS（只生成前3段用于测试）
from utils.tts_generator_v1_4 import GeminiTTSGeneratorV14, VoiceManager
from utils.voice_config_parser import VoiceConfigParser

voice_config = VoiceConfigParser.parse_voice_config()
voice_manager = VoiceManager(voice_config=voice_config)
tts_generator = GeminiTTSGeneratorV14(
    api_key=Config.MINIMAX_API_KEY,
    group_id=Config.MINIMAX_GROUP_ID,
    model_name="speech-2.8-hd",
    voice_manager=voice_manager,
    enable_cache=True
)

audio_dir = Path(f"output/audio_segments/test_{current_asr_hash}")

# 检查缓存
if audio_dir.exists():
    audio_dir_mtime = audio_dir.stat().st_mtime
    translation_file_mtime = translations_file.stat().st_mtime

    if audio_dir_mtime < translation_file_mtime:
        print(f"⚠️  音频缓存早于翻译文件，删除旧缓存...")
        import shutil
        shutil.rmtree(audio_dir)
        print(f"✓ 已删除旧音频缓存")

audio_dir.mkdir(parents=True, exist_ok=True)

# 只生成前3段
test_segments = translations[:3]
audio_files = []

for i, translation in enumerate(test_segments):
    segment_id = translation['segment_id']
    text = translation['translated_text']
    audio_file = audio_dir / f"segment_{segment_id:04d}.mp3"

    if audio_file.exists() and audio_file.stat().st_size > 1000:
        print(f"[Segment {segment_id}] ⏩ 跳过（已存在）")
        duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                       '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_file)]
        duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
        audio_files.append({'file': str(audio_file), 'duration': duration})
        continue

    print(f"[Segment {segment_id}] 生成音频...")
    tts_generator.generate_audio(text=text, output_path=audio_file)

    duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                   '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_file)]
    duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
    audio_files.append({'file': str(audio_file), 'duration': duration})
    print(f"  ✓ {duration:.1f}秒")

# 合并音频
test_output = Path("output/test_main_audio.mp3")
with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
    for af in audio_files:
        abs_path = Path(af['file']).absolute()
        f.write(f"file '{abs_path}'\n")
    concat_list = f.name

cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', concat_list,
       '-ar', '24000', '-ac', '1', '-b:a', '128k', '-y', str(test_output)]
subprocess.run(cmd, capture_output=True, check=True)
Path(concat_list).unlink()

print(f"\n✅ 测试音频已生成: {test_output}")
print(f"✅ 请播放此文件验证内容是否正确")
print(f"✅ 应该以'我现在是Lovable的增长负责人'开头")
