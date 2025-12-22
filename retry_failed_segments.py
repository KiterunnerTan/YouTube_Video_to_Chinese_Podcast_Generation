"""重试失败的TTS segments"""
import json
import time
from pathlib import Path
from config import Config
from utils.tts_generator_v1_4 import GeminiTTSGeneratorV14, VoiceManager


def main():
    Config.validate()
    Config.setup_proxy()

    # 读取清单
    manifest_file = Path("output/audio_segments/gemini_3_final/manifest.json")
    with open(manifest_file, 'r') as f:
        manifest = json.load(f)

    # 找出失败的segments
    failed_results = [r for r in manifest['results'] if r['status'] == 'failed']

    if not failed_results:
        print("所有segments都已成功!")
        return

    print(f"\n找到{len(failed_results)}个失败的segments:")
    for r in failed_results:
        print(f"  - 段{r['segment_id']}")

    # 读取翻译文件
    translation_file = Path(manifest['source_file'])
    with open(translation_file, 'r') as f:
        data = json.load(f)
        translations = data['translations']

    # 合并文本
    full_text = ""
    for trans in translations:
        full_text += trans['translated_text'] + "\n"

    # 重新分段
    from utils.text_segmenter import TextSegmenter
    segmenter = TextSegmenter(max_segment_length=1200)
    segments = segmenter.segment_text(full_text)

    # 创建TTS生成器
    voice_manager = VoiceManager()
    tts_generator = GeminiTTSGeneratorV14(
        api_key=Config.GEMINI_API_KEY,
        model_name="gemini-2.5-pro-preview-tts",
        voice_manager=voice_manager,
        enable_cache=True
    )

    output_dir = Path("output/audio_segments/gemini_3_final")

    # 重试失败的segments
    print(f"\n开始重试...\n")

    retry_count = 0
    for result in failed_results:
        segment_id = result['segment_id']
        segment = segments[segment_id]
        text = segment['text']
        char_count = segment['char_count']

        print(f"[段{segment_id}] 重试 ({char_count}字符)...")

        audio_filename = f"segment_{segment_id:04d}.mp3"
        audio_path = output_dir / audio_filename

        try:
            tts_generator.generate_audio(text=text, output_path=audio_path)
            print(f"[段{segment_id}] ✓ 重试成功!\n")
            retry_count += 1

            # 更新manifest中的状态
            for r in manifest['results']:
                if r['segment_id'] == segment_id:
                    r['status'] = 'success'
                    r['audio_file'] = str(audio_path)
                    r['char_count'] = char_count
                    if 'error' in r:
                        del r['error']

            # 延迟10秒
            time.sleep(10)

        except Exception as e:
            print(f"[段{segment_id}] ✗ 重试仍失败: {str(e)}\n")

    # 更新manifest
    manifest['success_count'] = sum(1 for r in manifest['results'] if r['status'] == 'success')
    manifest['failed_count'] = len(manifest['results']) - manifest['success_count']

    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n重试完成!")
    print(f"本次成功: {retry_count}/{len(failed_results)}")
    print(f"总成功率: {manifest['success_count']}/{manifest['total_segments']}")

    # 如果全部成功,合并音频
    if manifest['failed_count'] == 0:
        print(f"\n所有segments都已成功!开始合并音频...")

        import subprocess
        import tempfile

        successful_results = [r for r in manifest['results'] if r['status'] == 'success']
        final_audio_file = Path("output/final_audio/gemini_3_podcast_final.mp3")
        final_audio_file.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for result in successful_results:
                f.write(f"file '{Path(result['audio_file']).absolute()}'\n")
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
            print(f"🎉 Gemini 3播客最终版生成完成!")
            print(f"{'='*60}")
            print(f"✓ 最终音频: {final_audio_file}")
            print(f"✓ 音频时长: {duration/60:.1f}分钟 ({duration:.0f}秒)")
            print(f"✓ 文件大小: {final_audio_file.stat().st_size / 1024 / 1024:.1f}MB")
            print(f"✓ 音频片段数: {len(successful_results)}")
            print(f"✓ Speaker: 2个 (speaker_0 + speaker_1)")
            print(f"✓ 分段大小: 1200字符")
            print(f"{'='*60}\n")

        finally:
            Path(concat_list).unlink()


if __name__ == "__main__":
    main()
