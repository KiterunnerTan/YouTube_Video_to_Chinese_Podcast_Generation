#!/usr/bin/env python3
"""重新生成播客描述文案"""
from pathlib import Path
from config import Config
import json
import re

# 设置代理
Config.setup_proxy()
Config.validate()

from utils.podcast_description_generator import PodcastDescriptionGenerator
from utils.podcast_name_parser import PodcastNameParser

print("=" * 80)
print("📝 重新生成播客描述文案")
print("=" * 80)

# 解析节目名
podcast_name = PodcastNameParser.parse_podcast_name()
print(f"✓ 播客名: {podcast_name}")

# 从 start_prompt.md 提取 YouTube URL
try:
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
    print(f"✓ YouTube URL: {youtube_url}")
except Exception:
    youtube_url = "www.youtube.com"
    print(f"⚠️  无法提取 YouTube URL，使用默认值")

# 查找匹配的 ASR 文件
asr_dir = Path("output/asr_results")
asr_file = None

if youtube_url and youtube_url != "www.youtube.com":
    for asr_path in asr_dir.glob("qwen_asr_*.json"):
        try:
            with open(asr_path, 'r', encoding='utf-8') as f:
                asr_data = json.load(f)
                metadata = asr_data.get('metadata', {})
                if metadata.get('youtube_url') == youtube_url:
                    asr_file = asr_path
                    print(f"✓ 找到匹配的ASR文件: {asr_file.name}")
                    break
        except:
            continue

if not asr_file:
    # 如果没找到匹配的，使用最新的 ASR 文件（包括 asr_processed.json）
    asr_files = sorted(asr_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if asr_files:
        asr_file = asr_files[0]
        print(f"⚠️  未找到精确匹配，使用最新的ASR文件: {asr_file.name}")
    else:
        print("❌ 未找到任何ASR文件")
        exit(1)

print()

# 生成描述
desc_generator = PodcastDescriptionGenerator(Config.GEMINI_API_KEY)

try:
    # 使用 generate_from_files 方法（与 auto_generate_podcast.py 一致）
    description = desc_generator.generate_from_files(
        start_prompt_file=Path("start_prompt.md"),
        asr_file=asr_file,
        video_url=youtube_url
    )

    if description:
        # 保存文案
        output_dir = Path("output/description")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{podcast_name}.txt"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(description)

        print("=" * 80)
        print("✅ 播客描述文案生成成功！")
        print("=" * 80)
        print(f"📁 保存位置: {output_file}")
        print()
        print("📄 文案内容:")
        print("-" * 80)
        print(description)
        print("-" * 80)
    else:
        print("❌ 描述生成失败：返回为空")
        exit(1)

except Exception as e:
    print(f"❌ 生成失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
