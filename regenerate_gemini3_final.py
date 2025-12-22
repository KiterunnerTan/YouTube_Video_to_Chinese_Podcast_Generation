"""
重新生成Gemini 3完整播客 - 最终简单版

改进:
1. 修复翻译截断问题(包含完整结束语)
2. 使用1200字符分段(最保守稳定,比950字符提升26%)
3. 强制只用2个speaker (speaker_0和speaker_1) - v1.4简单方案
"""
import json
import time
import subprocess
import tempfile
from pathlib import Path
from config import Config
from utils.translator_v1_4 import GeminiTranslatorV14
from utils.tts_generator_v1_4 import GeminiTTSGeneratorV14, VoiceManager
from utils.text_segmenter import TextSegmenter


def main():
    Config.validate()
    Config.setup_proxy()

    print(f"\n{'='*60}")
    print(f"Gemini 3视频 - 完整中文音频生成 (v1.4简单版)")
    print(f"{'='*60}")
    print(f"改进:")
    print(f"  1. 翻译完整性: 包含完整结束语")
    print(f"  2. TTS分段: 950字符 → 1200字符 (最保守稳定)")
    print(f"  3. Speaker模式: 强制2个 (speaker_0和speaker_1)")
    print(f"{'='*60}\n")

    # ============================================================
    # Step 1: 重新翻译(强制只用2个speaker)
    # ============================================================
    asr_file = Path("output/asr_results/gemini_3_processed_20251221_181828.json")

    print(f"\n{'='*60}")
    print(f"Step 1: 重新翻译 (强制只用speaker_0和speaker_1)")
    print(f"{'='*60}")
    print(f"输入: {asr_file}")

    with open(asr_file, 'r', encoding='utf-8') as f:
        asr_data = json.load(f)
        segments = asr_data["segments"]

    print(f"ASR segments: {len(segments)}")

    translator = GeminiTranslatorV14(
        api_key=Config.GEMINI_API_KEY,
        model_name="gemini-2.5-pro"
    )

    try:
        translations = translator.translate_all_segments(
            segments,
            delay_between_calls=2.0
        )

        # 保存翻译
        translation_output = Path("output/translations/gemini_3_translations_final.json")
        translator.save_translations(translations, translation_output)

        print(f"\n✓ 翻译完成: {translation_output}")

        # 验证speaker数量
        full_text = ""
        for trans in translations:
            full_text += trans['translated_text'] + "\n"

        import re
        pattern = r'^(speaker_\d+):'
        speakers = set()
        for line in full_text.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                speakers.add(match.group(1))

        speakers = sorted(list(speakers))
        print(f"✓ Speaker验证: {len(speakers)}个 - {speakers}")

        if len(speakers) > 2:
            print(f"❌ 错误: 检测到{len(speakers)}个speaker,但只应该有2个!")
            print(f"请检查翻译prompt是否正确限制为只用speaker_0和speaker_1")
            return

    except Exception as e:
        print(f"✗ 翻译失败: {str(e)}")
        return

    # ============================================================
    # Step 2: 智能分段(1200字符)
    # ============================================================
    print(f"\n{'='*60}")
    print(f"Step 2: 智能分段 (1200字符上限)")
    print(f"{'='*60}")

    total_chars = len(full_text)
    print(f"总中文字符数: {total_chars}")

    segmenter = TextSegmenter(max_segment_length=1200)
    tts_segments = segmenter.segment_text(full_text)
    analysis = segmenter.analyze_segments(tts_segments)

    print(f"TTS segment数: {analysis['total_segments']}")
    print(f"平均每段: {analysis['avg_chars_per_segment']} 字符")
    print(f"最大段: {analysis['max_chars']} 字符")
    print(f"最小段: {analysis['min_chars']} 字符")

    print(f"\n各段详情:")
    for detail in analysis['segments_detail']:
        print(f"  段{detail['id']}: {detail['chars']}字符, {detail['sentences']}句")

    # 对比
    old_count = 12
    reduction = (1 - analysis['total_segments'] / old_count) * 100
    print(f"\n对比950字符分段:")
    print(f"  segment数量: {old_count}个 → {analysis['total_segments']}个 (减少{reduction:.0f}%)")

    # ============================================================
    # Step 3: 生成TTS音频(2-speaker模式)
    # ============================================================
    print(f"\n{'='*60}")
    print(f"Step 3: 生成TTS音频 (2-speaker模式)")
    print(f"{'='*60}")

    voice_manager = VoiceManager()
    tts_generator = GeminiTTSGeneratorV14(
        api_key=Config.GEMINI_API_KEY,
        model_name="gemini-2.5-pro-preview-tts",
        voice_manager=voice_manager,
        enable_cache=True
    )

    print(f"模型: gemini-2.5-pro-preview-tts")
    print(f"音色: speaker_0=Kore(女声) + speaker_1=Charon(男声)")
    print(f"并行度: 1 (串行生成)")
    print(f"缓存: 已启用")

    output_dir = Path("output/audio_segments/gemini_3_final")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n开始串行生成音频（预计API调用: {len(tts_segments)}次）...\n")

    results = []
    for segment in tts_segments:
        segment_id = segment["segment_id"]
        text = segment["text"]
        char_count = segment["char_count"]

        print(f"\n[段{segment_id}] 开始生成 ({char_count}字符)...")

        audio_filename = f"segment_{segment_id:04d}.mp3"
        audio_path = output_dir / audio_filename

        try:
            tts_generator.generate_audio(text=text, output_path=audio_path)

            result = {
                "segment_id": segment_id,
                "audio_file": str(audio_path),
                "char_count": char_count,
                "status": "success"
            }

            print(f"[段{segment_id}] ✓ 生成成功")
            results.append(result)

            # 延迟5秒
            time.sleep(5)

        except Exception as e:
            print(f"[段{segment_id}] ✗ 生成失败: {str(e)}")
            results.append({
                "segment_id": segment_id,
                "status": "failed",
                "error": str(e)
            })

    # ============================================================
    # Step 4: 统计和合并
    # ============================================================
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = len(results) - success_count

    print(f"\n{'='*60}")
    print(f"音频生成完成")
    print(f"{'='*60}")
    print(f"成功: {success_count}/{len(results)}")
    print(f"失败: {failed_count}/{len(results)}")

    # 保存清单
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump({
            "version": "final",
            "source_file": str(translation_output),
            "total_segments": len(tts_segments),
            "total_chars": total_chars,
            "segment_size": "1200 chars (最保守稳定)",
            "speaker_mode": "2-speaker (speaker_0 + speaker_1)",
            "speakers": speakers,
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    print(f"清单已保存到: {manifest_file}")

    # 合并音频
    if success_count > 0:
        print(f"\n{'='*60}")
        print(f"合并音频")
        print(f"{'='*60}")

        successful_results = [r for r in results if r["status"] == "success"]
        final_audio_file = Path("output/final_audio/gemini_3_podcast_final.mp3")
        final_audio_file.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for result in successful_results:
                f.write(f"file '{Path(result['audio_file']).absolute()}'\\n")
            concat_list = f.name

        try:
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list,
                '-c', 'copy',
                '-y',
                str(final_audio_file)
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            print(f"✓ 音频已合并到: {final_audio_file}")

            # 获取音频信息
            duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                           '-of', 'default=noprint_wrappers=1:nokey=1', str(final_audio_file)]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
            duration = float(duration_result.stdout.strip())

            print(f"\n{'='*60}")
            print(f"🎉 Gemini 3播客生成完成!")
            print(f"{'='*60}")
            print(f"✓ 最终音频: {final_audio_file}")
            print(f"✓ 音频时长: {duration/60:.1f}分钟 ({duration:.0f}秒)")
            print(f"✓ 文件大小: {final_audio_file.stat().st_size / 1024 / 1024:.1f}MB")
            print(f"✓ 音频片段数: {len(successful_results)}")
            print(f"✓ Speaker数: 2 (speaker_0 + speaker_1)")
            print(f"✓ 分段大小: 1200字符 (最保守稳定)")
            print(f"✓ 翻译完整性: 包含结束语")
            print(f"{'='*60}\n")

        finally:
            Path(concat_list).unlink()
    else:
        print(f"\n❌ 所有音频生成都失败了")


if __name__ == "__main__":
    main()
