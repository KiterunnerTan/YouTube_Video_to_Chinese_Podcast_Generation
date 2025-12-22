"""智能文本分段模块 - 用于TTS长文本处理"""
import json
import re
from typing import List, Dict, Any
from pathlib import Path


class TextSegmenter:
    """智能文本分段器，按语义边界分段，避免打断句子"""

    def __init__(self, max_segment_length: int = 1200):
        """
        初始化分段器

        Args:
            max_segment_length: 每段最大字符数（默认1200，最保守稳定）
        """
        self.max_segment_length = max_segment_length

    def segment_text(self, text: str) -> List[Dict[str, Any]]:
        """
        将长文本按语义边界智能分段

        Args:
            text: 完整的翻译文本

        Returns:
            分段列表，每个元素包含：
            {
                "segment_id": 段号（从0开始）,
                "text": 段文本内容,
                "char_count": 字符数,
                "sentence_count": 句子数
            }
        """
        # 按行分割（每行是一个说话人的一句话）
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        segments = []
        current_segment = []
        current_length = 0
        segment_id = 0

        for line in lines:
            line_length = len(line)

            # 检查是否需要开始新段
            # 规则：当前段 + 新行超过限制，且当前段不为空
            if current_length + line_length > self.max_segment_length and current_segment:
                # 保存当前段
                segment_text = '\n'.join(current_segment)
                segments.append({
                    "segment_id": segment_id,
                    "text": segment_text,
                    "char_count": current_length,
                    "sentence_count": len(current_segment)
                })

                # 开始新段
                segment_id += 1
                current_segment = []
                current_length = 0

            # 添加当前行到段
            current_segment.append(line)
            current_length += line_length + 1  # +1 for newline

        # 保存最后一段
        if current_segment:
            segment_text = '\n'.join(current_segment)
            segments.append({
                "segment_id": segment_id,
                "text": segment_text,
                "char_count": current_length,
                "sentence_count": len(current_segment)
            })

        return segments

    def analyze_segments(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析分段结果

        Returns:
            分段统计信息
        """
        total_segments = len(segments)
        total_chars = sum(seg["char_count"] for seg in segments)
        avg_chars = total_chars / total_segments if total_segments > 0 else 0
        max_chars = max(seg["char_count"] for seg in segments) if segments else 0
        min_chars = min(seg["char_count"] for seg in segments) if segments else 0

        return {
            "total_segments": total_segments,
            "total_chars": total_chars,
            "avg_chars_per_segment": round(avg_chars, 1),
            "max_chars": max_chars,
            "min_chars": min_chars,
            "segments_detail": [
                {
                    "id": seg["segment_id"],
                    "chars": seg["char_count"],
                    "sentences": seg["sentence_count"],
                    "preview": seg["text"][:80] + "..." if len(seg["text"]) > 80 else seg["text"]
                }
                for seg in segments
            ]
        }

    def segment_translation_file(self, input_file: Path) -> List[Dict[str, Any]]:
        """
        从翻译JSON文件中读取并分段

        Args:
            input_file: 翻译JSON文件路径

        Returns:
            分段列表
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 获取翻译文本
        translated_text = data['translations'][0]['translated_text']

        # 分段
        segments = self.segment_text(translated_text)

        return segments


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="智能文本分段工具")
    parser.add_argument("input_file", help="输入翻译JSON文件")
    parser.add_argument("-m", "--max-length", type=int, default=1200,
                       help="每段最大字符数（默认1200）")
    parser.add_argument("-o", "--output", help="输出分段JSON文件（可选）")

    args = parser.parse_args()

    # 创建分段器
    segmenter = TextSegmenter(max_segment_length=args.max_length)

    # 分段
    segments = segmenter.segment_translation_file(Path(args.input_file))

    # 分析
    analysis = segmenter.analyze_segments(segments)

    # 打印结果
    print(f"\n{'='*60}")
    print(f"分段分析结果")
    print(f"{'='*60}")
    print(f"总段数：{analysis['total_segments']}")
    print(f"总字符数：{analysis['total_chars']}")
    print(f"平均每段：{analysis['avg_chars_per_segment']} 字符")
    print(f"最大段：{analysis['max_chars']} 字符")
    print(f"最小段：{analysis['min_chars']} 字符")
    print(f"\n各段详情：")
    for detail in analysis['segments_detail']:
        print(f"  段{detail['id']}: {detail['chars']}字符, {detail['sentences']}句")
        print(f"    预览: {detail['preview']}")

    # 保存到文件（可选）
    if args.output:
        output_data = {
            "source_file": str(args.input_file),
            "max_segment_length": args.max_length,
            "analysis": analysis,
            "segments": segments
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n分段结果已保存到: {args.output}")
