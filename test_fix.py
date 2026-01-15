#!/usr/bin/env python3
"""测试修复：验证ASR文件处理后是否有formatted_text"""
import json
from pathlib import Path
from utils.text_processor import TextProcessor

# 读取ASR文件
asr_file = Path("output/asr_results/qwen_asr_20260102_153544.json")
with open(asr_file, 'r', encoding='utf-8') as f:
    asr_data = json.load(f)

print("=" * 80)
print("测试：ASR文件处理验证")
print("=" * 80)

# 检查原始ASR文件
segments = asr_data.get('segments', [])
print(f"\n✓ 原始ASR段落数: {len(segments)}")
print(f"✓ 原始第一段是否有formatted_text: {'formatted_text' in segments[0]}")

if 'formatted_text' not in segments[0]:
    print("\n⚠️  正在处理ASR文件，生成formatted_text...")
    processor = TextProcessor(segment_duration_minutes=3)
    processed_result = processor.process_asr_result(asr_data)
    segments = processed_result.get('segments', [])

    print(f"✓ 处理后段落数: {len(segments)}")
    print(f"✓ 处理后是否有formatted_text: {'formatted_text' in segments[0]}")

    # 显示第一段的内容
    if segments:
        first_segment = segments[0]
        print(f"\n第一段内容预览:")
        print(f"  segment_id: {first_segment.get('segment_id')}")
        print(f"  formatted_text前100字符:\n    {first_segment.get('formatted_text', '')[:100]}...")

        # 验证formatted_text确实包含原始英文
        formatted_text = first_segment.get('formatted_text', '')
        if "You're ahead of growth at lovable" in formatted_text:
            print("\n✅ 验证成功：formatted_text包含正确的原始英文文本！")
        else:
            print("\n❌ 验证失败：formatted_text内容不匹配")
            print(f"实际内容: {formatted_text[:200]}")
else:
    print("✓ ASR文件已包含formatted_text")
    print(f"\n第一段formatted_text前100字符:\n  {segments[0].get('formatted_text', '')[:100]}...")

print("\n" + "=" * 80)
