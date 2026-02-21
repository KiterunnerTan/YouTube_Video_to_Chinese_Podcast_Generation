"""调试时间戳生成流程 - 测试两阶段提取"""
from pathlib import Path
import json
from config import Config
from utils.podcast_description_generator import PodcastDescriptionGenerator

Config.setup_proxy()

# 使用当前播客的ASR文件
ASR_FILE = Path("output/podcasts/646a2bf1230e/asr.json")

print("=" * 80)
print("调试时间戳生成流程")
print("=" * 80)

# 初始化生成器
generator = PodcastDescriptionGenerator(Config.GEMINI_API_KEY)

# 1. 加载翻译段落
print("\n步骤1: 加载翻译段落...")
translation_segments = generator.load_translation_segments(ASR_FILE)
print(f"✓ 加载了 {len(translation_segments)} 个翻译段落")

if translation_segments:
    # 显示前3个段落的时间戳
    print("\n前3个段落的时间信息:")
    for i, seg in enumerate(translation_segments[:3]):
        start_ms = seg.get('start_time_ms', 0)
        end_ms = seg.get('end_time_ms', 0)
        text_preview = seg.get('translated_text', '')[:50]
        print(f"  [{i}] {start_ms//60000}:{(start_ms%60000)//1000:02d} - {end_ms//60000}:{(end_ms%60000)//1000:02d}")
        print(f"      {text_preview}...")

# 2. 提取核心话题
print("\n" + "=" * 80)
print("步骤2: 提取核心话题（调用Gemini API）...")
print("=" * 80)

podcast_name = "Head of Claude Code: What happens after coding is solved | Boris Cherny"
guest_name = "Boris Cherny"

topics, questions = generator.extract_core_topics(
    podcast_name, guest_name, translation_segments
)

print(f"\n结果:")
print(f"  topics 数量: {len(topics)}")
print(f"  questions 数量: {len(questions)}")

if topics:
    print("\n提取到的话题:")
    for i, topic in enumerate(topics):
        print(f"  [{i+1}] {topic.get('title', 'N/A')}")
        print(f"      key_sentence: {topic.get('key_sentence', 'N/A')[:50]}...")
else:
    print("\n⚠️ 未提取到任何话题！这就是时间戳缺失的原因。")

# 3. 匹配时间戳
if topics:
    print("\n" + "=" * 80)
    print("步骤3: 匹配时间戳...")
    print("=" * 80)

    topics_with_timestamps = generator.match_timestamps(topics, translation_segments)

    print(f"\n最终结果:")
    for t in topics_with_timestamps:
        print(f"  {t['timestamp']} {t['title']}")
else:
    print("\n跳过时间戳匹配（因为没有提取到话题）")

print("\n" + "=" * 80)
print("调试完成")
print("=" * 80)
