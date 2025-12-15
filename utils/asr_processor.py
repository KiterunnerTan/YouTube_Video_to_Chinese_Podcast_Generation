"""Alibaba Cloud DashScope Qwen3-ASR processor"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from http import HTTPStatus
import dashscope
from dashscope.audio.asr import Recognition


class AudioSplitter:
    """Split audio/video files into segments for ASR processing"""

    def __init__(self, segment_duration_seconds: int = 180):
        """
        Initialize audio splitter

        Args:
            segment_duration_seconds: Duration of each segment in seconds (default: 180 = 3 minutes)
        """
        self.segment_duration = segment_duration_seconds

    def get_audio_duration(self, file_path: Path) -> float:
        """
        Get audio/video file duration using ffprobe

        Args:
            file_path: Path to audio/video file

        Returns:
            Duration in seconds
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(file_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return float(info['format']['duration'])

    def split_audio(
        self,
        input_file: Path,
        output_dir: Path
    ) -> List[Path]:
        """
        Split audio/video file into segments

        Args:
            input_file: Path to input audio/video file
            output_dir: Directory to save segments

        Returns:
            List of segment file paths
        """
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Get duration
        duration = self.get_audio_duration(input_file)
        num_segments = int(duration / self.segment_duration) + 1

        print(f"Audio duration: {duration:.2f}s")
        print(f"Splitting into {num_segments} segments ({self.segment_duration}s each)...")

        segment_files = []

        for i in range(num_segments):
            start_time = i * self.segment_duration
            output_file = output_dir / f"segment_{i:04d}.mp3"

            cmd = [
                'ffmpeg',
                '-i', str(input_file),
                '-ss', str(start_time),
                '-t', str(self.segment_duration),
                '-c:a', 'libmp3lame',
                '-b:a', '128k',
                '-ar', '16000',  # 16kHz sample rate for ASR
                '-ac', '1',      # Mono
                '-y',
                str(output_file)
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            segment_files.append(output_file)
            print(f"Created segment {i+1}/{num_segments}: {output_file.name}")

        return segment_files


class Qwen3ASRProcessor:
    """Qwen3-ASR-Flash processor using DashScope SDK"""

    def __init__(
        self,
        api_key: str,
        model: str = 'paraformer-realtime-v2',
        segment_duration_seconds: int = 180,
        enable_diarization: bool = True,
        speaker_count: Optional[int] = None
    ):
        """
        Initialize Qwen3-ASR processor

        Args:
            api_key: DashScope API Key
            model: Model name (default: paraformer-realtime-v2)
            segment_duration_seconds: Segment duration for splitting (default: 180s = 3min)
            enable_diarization: Enable speaker diarization (default: True)
            speaker_count: Expected number of speakers (optional, auto-detect if None)
        """
        self.api_key = api_key
        self.model = model
        self.enable_diarization = enable_diarization
        self.speaker_count = speaker_count
        dashscope.api_key = api_key
        self.splitter = AudioSplitter(segment_duration_seconds)

    def transcribe_file(
        self,
        audio_file: Path,
        language_hints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Transcribe a single audio file (must be < 3 minutes)

        Args:
            audio_file: Path to audio file
            language_hints: Language hints (e.g., ['zh', 'en'])

        Returns:
            Transcription result
        """
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        print(f"Transcribing: {audio_file.name}")

        try:
            # Create Recognition instance
            recognizer = Recognition(
                model=self.model,
                format='mp3',
                sample_rate=16000,
                callback=None
            )

            # Prepare call parameters
            call_params = {
                'file': str(audio_file.absolute()),
                'diarization_enabled': self.enable_diarization
            }

            # Add speaker count if specified
            if self.speaker_count is not None:
                call_params['speaker_count'] = self.speaker_count

            # Transcribe local file with speaker diarization
            result = recognizer.call(**call_params)

            if result.status_code == HTTPStatus.OK:
                return result.output
            else:
                raise RuntimeError(
                    f"ASR failed: {result.status_code} - {getattr(result, 'message', 'Unknown error')}"
                )

        except Exception as e:
            raise RuntimeError(f"Failed to transcribe {audio_file.name}: {str(e)}")

    def process_video_file(
        self,
        video_file: Path,
        output_dir: Optional[Path] = None,
        language_hints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process a video/audio file (auto-split if > 3 minutes)

        Args:
            video_file: Path to video/audio file
            output_dir: Directory to save segments (default: temp dir)
            language_hints: Language hints

        Returns:
            Complete transcription result
        """
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_file}")

        # Create temp directory for segments
        if output_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="asr_segments_")
            output_dir = Path(temp_dir)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n=== Processing: {video_file.name} ===")

        # Get duration and check if splitting is needed
        duration = self.splitter.get_audio_duration(video_file)

        if duration <= self.splitter.segment_duration:
            # File is short enough, process directly
            print(f"File duration {duration:.2f}s <= {self.splitter.segment_duration}s, processing directly...")
            result = self.transcribe_file(video_file, language_hints)
            return self._format_single_result(result, video_file)

        # Split audio into segments
        print(f"\nFile duration {duration:.2f}s > {self.splitter.segment_duration}s, splitting...")
        segment_files = self.splitter.split_audio(video_file, output_dir)

        # Transcribe each segment
        print(f"\n=== Transcribing {len(segment_files)} segments ===")
        all_results = []

        for i, segment_file in enumerate(segment_files, 1):
            print(f"\n[{i}/{len(segment_files)}] ", end="")
            result = self.transcribe_file(segment_file, language_hints)
            all_results.append({
                'segment_id': i - 1,
                'segment_file': str(segment_file),
                'result': result
            })

        # Merge results
        print(f"\n=== Merging {len(all_results)} segment results ===")
        merged_result = self._merge_results(all_results, video_file)

        print(f"✓ Transcription completed!")
        return merged_result

    def _format_single_result(
        self,
        result: Dict[str, Any],
        video_file: Path
    ) -> Dict[str, Any]:
        """Format single file result"""
        return {
            'source_file': str(video_file),
            'total_segments': 1,
            'segments': [{
                'segment_id': 0,
                'start_time_ms': 0,
                'end_time_ms': None,
                'transcription': result
            }],
            'raw_output': result
        }

    def _merge_results(
        self,
        segment_results: List[Dict[str, Any]],
        video_file: Path
    ) -> Dict[str, Any]:
        """
        Merge segment results into complete result

        Args:
            segment_results: List of segment results
            video_file: Original video file

        Returns:
            Merged result
        """
        merged_segments = []

        for seg_result in segment_results:
            segment_id = seg_result['segment_id']
            start_time_ms = segment_id * self.splitter.segment_duration * 1000
            end_time_ms = (segment_id + 1) * self.splitter.segment_duration * 1000

            merged_segments.append({
                'segment_id': segment_id,
                'start_time_ms': start_time_ms,
                'end_time_ms': end_time_ms,
                'segment_file': seg_result['segment_file'],
                'transcription': seg_result['result']
            })

        return {
            'source_file': str(video_file),
            'total_segments': len(merged_segments),
            'segments': merged_segments,
            'model': self.model
        }

    def save_result(self, result: Dict[str, Any], output_path: Path):
        """Save transcription result to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Result saved to: {output_path}")


if __name__ == "__main__":
    # Example usage
    import argparse
    from config import Config

    parser = argparse.ArgumentParser(description="Qwen3-ASR processor")
    parser.add_argument("input_file", help="Input video/audio file")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument(
        "-l", "--languages",
        nargs='+',
        default=['zh', 'en'],
        help="Language hints (default: zh en)"
    )

    args = parser.parse_args()

    Config.validate()
    Config.create_directories()

    processor = Qwen3ASRProcessor(
        api_key=Config.DASHSCOPE_API_KEY
    )

    try:
        # Process file
        result = processor.process_video_file(
            Path(args.input_file),
            language_hints=args.languages
        )

        # Save result
        if args.output:
            output_path = Path(args.output)
        else:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Config.ASR_RESULTS_DIR / f"qwen_asr_{timestamp}.json"

        processor.save_result(result, output_path)
        print(f"\n✓ Success! Result saved to: {output_path}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        exit(1)
