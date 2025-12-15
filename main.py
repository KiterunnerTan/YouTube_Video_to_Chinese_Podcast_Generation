"""Main CLI entry point for AI Video to Audio application"""
import sys
import click
from pathlib import Path
from datetime import datetime

from config import Config
from utils.youtube_downloader import YouTubeDownloader
from utils.asr_processor import Qwen3ASRProcessor
from utils.paraformer_asr import ParaformerASRProcessor
from utils.oss_uploader import OSSUploader
from utils.text_processor import TextProcessor
from utils.translator import GeminiTranslator
from utils.tts_generator import GeminiTTSGenerator
from utils.audio_merger import AudioMerger


@click.group()
def cli():
    """AI Video to Audio - Convert videos to Chinese podcast audio"""
    pass


@cli.command()
@click.argument('url')
@click.option('-c', '--cookie', help='Path to cookies.txt file')
@click.option('-a', '--audio-only', is_flag=True, help='Download audio only')
def download(url, cookie, audio_only):
    """Download video/audio from YouTube URL"""
    try:
        Config.create_directories()
        downloader = YouTubeDownloader(Config.DOWNLOADS_DIR)

        if audio_only:
            file_path = downloader.download_audio_only(url, cookie_file=cookie)
        else:
            file_path = downloader.download(url, cookie_file=cookie)

        click.echo(f"\n✓ Downloaded: {file_path}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_file')
@click.option('-l', '--languages', multiple=True, default=['zh', 'en'], help='Language hints (can specify multiple)')
@click.option('-o', '--output', help='Output JSON file path')
def asr(input_file, languages, output):
    """Perform ASR transcription using Qwen3-ASR-Flash (supports local files)"""
    try:
        Config.validate()
        Config.create_directories()

        processor = Qwen3ASRProcessor(
            api_key=Config.DASHSCOPE_API_KEY
        )

        # Process video/audio file
        result = processor.process_video_file(
            Path(input_file),
            language_hints=list(languages)
        )

        # Save result
        if output:
            output_path = Path(output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Config.ASR_RESULTS_DIR / f"qwen_asr_{timestamp}.json"

        processor.save_result(result, output_path)
        click.echo(f"\n✓ ASR completed: {output_path}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_file')
@click.option('-o', '--output', help='Output JSON file path')
def process(input_file, output):
    """Process ASR results (extract fields and segment)"""
    try:
        Config.create_directories()

        import json
        with open(input_file, 'r', encoding='utf-8') as f:
            asr_result = json.load(f)

        processor = TextProcessor(segment_duration_minutes=Config.SEGMENT_DURATION_MINUTES)
        processed = processor.process_asr_result(asr_result)

        if output:
            output_path = Path(output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Config.ASR_RESULTS_DIR / f"processed_{timestamp}.json"

        processor.save_processed_result(processed, output_path)
        click.echo(f"\n✓ Processing completed: {output_path}")
        click.echo(f"  Total segments: {processed['total_segments']}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_file')
@click.option('-o', '--output', help='Output JSON file path')
def translate(input_file, output):
    """Translate segments using Gemini"""
    try:
        Config.validate()
        Config.setup_proxy()  # Setup proxy for Google services
        Config.create_directories()

        import json
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            segments = data['segments']

        translator = GeminiTranslator(api_key=Config.GEMINI_API_KEY)
        translations = translator.translate_all_segments(segments)

        if output:
            output_path = Path(output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Config.TRANSLATIONS_DIR / f"translations_{timestamp}.json"

        translator.save_translations(translations, output_path)
        click.echo(f"\n✓ Translation completed: {output_path}")
        click.echo(f"  Total segments: {len(translations)}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('input_file')
@click.option('-o', '--output-dir', help='Output directory for audio files')
@click.option('-m', '--manifest', help='Output manifest JSON file')
def tts(input_file, output_dir, manifest):
    """Generate audio using Gemini TTS"""
    try:
        Config.validate()
        Config.setup_proxy()  # Setup proxy for Google services
        Config.create_directories()

        import json
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            translations = data['translations']

        tts_generator = GeminiTTSGenerator(api_key=Config.GEMINI_API_KEY)

        output_directory = Path(output_dir) if output_dir else Config.AUDIO_SEGMENTS_DIR
        audio_segments = tts_generator.generate_audio_for_segments(
            translations,
            output_dir=output_directory
        )

        if manifest:
            manifest_path = Path(manifest)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            manifest_path = Config.AUDIO_SEGMENTS_DIR / f"manifest_{timestamp}.json"

        tts_generator.save_audio_manifest(audio_segments, manifest_path)
        click.echo(f"\n✓ TTS completed: {manifest_path}")
        click.echo(f"  Total segments: {len(audio_segments)}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('manifest_file')
@click.option('-o', '--output', required=True, help='Output audio file path')
def merge(manifest_file, output):
    """Merge audio segments into final audio"""
    try:
        Config.create_directories()

        merger = AudioMerger()
        output_path = merger.merge_from_manifest(
            Path(manifest_file),
            Path(output)
        )

        click.echo(f"\n✓ Merge completed: {output_path}")

    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('video_file')
@click.option('-o', '--output', help='Output audio file path')
@click.option('-l', '--languages', multiple=True, default=['zh', 'en'], help='Language hints')
@click.option('--enable-diarization/--no-diarization', default=True, help='Enable speaker diarization (default: enabled)')
@click.option('-s', '--speaker-count', type=int, help='Expected number of speakers (optional, auto-detect if not specified)')
def full_pipeline(video_file, output, languages, enable_diarization, speaker_count):
    """Run the complete pipeline: ASR → Process → Translate → TTS → Merge

    By default, uses Paraformer with speaker diarization (requires OSS configuration).
    Use --no-diarization to disable speaker diarization and skip OSS upload.
    """
    try:
        Config.validate()
        Config.setup_proxy()  # Setup proxy for Google services
        Config.create_directories()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        click.echo("\n=== Starting Full Pipeline ===")

        # Step 1: ASR
        click.echo("\n[1/5] ASR Transcription...")

        if enable_diarization:
            # Check OSS configuration for speaker diarization
            if not all([Config.OSS_ACCESS_KEY_ID, Config.OSS_ACCESS_KEY_SECRET, Config.OSS_BUCKET_NAME]):
                click.echo("✗ Error: Speaker diarization requires OSS configuration in .env file", err=True)
                click.echo("  Required: OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME", err=True)
                click.echo("  Use --no-diarization to skip speaker diarization", err=True)
                sys.exit(1)

            # Initialize OSS uploader
            oss_uploader = OSSUploader(
                access_key_id=Config.OSS_ACCESS_KEY_ID,
                access_key_secret=Config.OSS_ACCESS_KEY_SECRET,
                bucket_name=Config.OSS_BUCKET_NAME,
                endpoint=Config.OSS_ENDPOINT
            )

            # Use Paraformer with speaker diarization
            asr_processor = ParaformerASRProcessor(
                api_key=Config.DASHSCOPE_API_KEY,
                oss_uploader=oss_uploader,
                enable_diarization=True,
                speaker_count=speaker_count
            )
        else:
            # Use Qwen3-ASR (no speaker diarization)
            click.echo("⚠ Speaker diarization disabled")
            asr_processor = Qwen3ASRProcessor(
                api_key=Config.DASHSCOPE_API_KEY
            )

        asr_result = asr_processor.process_video_file(
            Path(video_file),
            language_hints=list(languages)
        )
        asr_path = Config.ASR_RESULTS_DIR / f"asr_{timestamp}.json"
        asr_processor.save_result(asr_result, asr_path)
        click.echo(f"✓ ASR completed")

        # Step 2: Process
        click.echo("\n[2/5] Processing ASR results...")
        text_processor = TextProcessor(segment_duration_minutes=Config.SEGMENT_DURATION_MINUTES)
        processed = text_processor.process_asr_result(asr_result)
        processed_path = Config.ASR_RESULTS_DIR / f"processed_{timestamp}.json"
        text_processor.save_processed_result(processed, processed_path)
        click.echo(f"✓ Processing completed ({processed['total_segments']} segments)")

        # Step 3: Translate
        click.echo("\n[3/5] Translating...")
        translator = GeminiTranslator(api_key=Config.GEMINI_API_KEY)
        translations = translator.translate_all_segments(processed['segments'])
        translations_path = Config.TRANSLATIONS_DIR / f"translations_{timestamp}.json"
        translator.save_translations(translations, translations_path)
        click.echo(f"✓ Translation completed")

        # Step 4: TTS
        click.echo("\n[4/5] Generating audio...")
        tts_generator = GeminiTTSGenerator(api_key=Config.GEMINI_API_KEY)
        audio_segments = tts_generator.generate_audio_for_segments(
            translations,
            output_dir=Config.AUDIO_SEGMENTS_DIR / timestamp
        )
        manifest_path = Config.AUDIO_SEGMENTS_DIR / f"manifest_{timestamp}.json"
        tts_generator.save_audio_manifest(audio_segments, manifest_path)
        click.echo(f"✓ TTS completed")

        # Step 5: Merge
        click.echo("\n[5/5] Merging audio segments...")
        merger = AudioMerger()
        if output:
            final_path = Path(output)
        else:
            final_path = Config.FINAL_DIR / f"podcast_{timestamp}.mp3"
        merger.merge_from_manifest(manifest_path, final_path)

        click.echo("\n=== Pipeline Completed ===")
        click.echo(f"✓ Final audio: {final_path}")

    except Exception as e:
        click.echo(f"\n✗ Pipeline failed: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
