"""Paraformer ASR processor using Transcription API with speaker diarization support"""
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from http import HTTPStatus
import dashscope
from dashscope.audio.asr import Transcription
import requests

from utils.oss_uploader import OSSUploader
from utils.asr_processor import AudioSplitter


class ParaformerASRProcessor:
    """Paraformer ASR processor using Transcription API for speaker diarization"""

    def __init__(
        self,
        api_key: str,
        oss_uploader: OSSUploader,
        model: str = 'paraformer-v2',
        segment_duration_seconds: int = 180,
        enable_diarization: bool = True,
        speaker_count: Optional[int] = None
    ):
        """
        Initialize Paraformer ASR processor with OSS uploader

        Args:
            api_key: DashScope API Key
            oss_uploader: OSS uploader instance for uploading audio files
            model: Model name (default: paraformer-v2)
            segment_duration_seconds: Segment duration for splitting (default: 180s)
            enable_diarization: Enable speaker diarization (default: True)
            speaker_count: Expected number of speakers (optional)
        """
        self.api_key = api_key
        self.oss_uploader = oss_uploader
        self.model = model
        self.enable_diarization = enable_diarization
        self.speaker_count = speaker_count
        dashscope.api_key = api_key
        self.splitter = AudioSplitter(segment_duration_seconds)

        print(f"✓ Paraformer ASR initialized with model: {model}")
        if enable_diarization:
            speaker_info = f"(expecting {speaker_count} speakers)" if speaker_count else "(auto-detect speakers)"
            print(f"✓ Speaker diarization enabled {speaker_info}")

    def transcribe_file_url(
        self,
        file_url: str,
        language_hints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Transcribe audio from URL using Transcription API

        Args:
            file_url: Public URL of audio file
            language_hints: Language hints (not directly supported by Transcription API)

        Returns:
            Transcription result

        Raises:
            RuntimeError: If transcription fails
        """
        print(f"Transcribing from URL...")

        try:
            # Prepare parameters
            kwargs = {
                'diarization_enabled': self.enable_diarization
            }

            if self.speaker_count is not None:
                kwargs['speaker_count'] = self.speaker_count

            # Call Transcription API
            response = Transcription.call(
                model=self.model,
                file_urls=[file_url],
                **kwargs
            )

            if response.status_code == HTTPStatus.OK:
                # Get the task result
                output = response.output

                # Extract transcription_url from results
                if 'results' in output and len(output['results']) > 0:
                    transcription_url = output['results'][0].get('transcription_url')

                    if transcription_url:
                        print(f"Downloading transcription from result URL...")
                        # Download the actual transcription content
                        trans_response = requests.get(transcription_url, timeout=30)
                        if trans_response.status_code == 200:
                            transcription_data = trans_response.json()
                            return transcription_data
                        else:
                            raise RuntimeError(f"Failed to download transcription: {trans_response.status_code}")
                    else:
                        raise RuntimeError("No transcription_url in results")
                else:
                    raise RuntimeError("No results in output")
            else:
                raise RuntimeError(
                    f"ASR failed: {response.status_code} - {getattr(response, 'message', 'Unknown error')}"
                )

        except Exception as e:
            raise RuntimeError(f"Failed to transcribe from URL: {str(e)}")

    def transcribe_file(
        self,
        audio_file: Path,
        language_hints: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Transcribe a local audio file (uploads to OSS first)

        Args:
            audio_file: Path to local audio file
            language_hints: Language hints

        Returns:
            Transcription result
        """
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        print(f"Transcribing: {audio_file.name}")

        try:
            # Upload to OSS
            file_url, oss_path = self.oss_uploader.upload_temp_file(audio_file)

            # Transcribe
            result = self.transcribe_file_url(file_url, language_hints)

            # Note: We don't delete the file immediately as it might be needed for retries
            # You can implement cleanup later if needed

            return result

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
        # Extract transcription from result
        transcription = result.get('transcripts', [{}])[0] if 'transcripts' in result else result

        return {
            'source_file': str(video_file),
            'total_segments': 1,
            'segments': [{
                'segment_id': 0,
                'start_time_ms': 0,
                'end_time_ms': None,
                'transcription': transcription
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

            # Extract transcription from result
            result = seg_result['result']
            transcription = result.get('transcripts', [{}])[0] if 'transcripts' in result else result

            merged_segments.append({
                'segment_id': segment_id,
                'start_time_ms': start_time_ms,
                'end_time_ms': end_time_ms,
                'segment_file': seg_result['segment_file'],
                'transcription': transcription
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

    parser = argparse.ArgumentParser(description="Paraformer ASR with speaker diarization")
    parser.add_argument("input_file", help="Input video/audio file")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument(
        "-s", "--speakers",
        type=int,
        help="Expected number of speakers (optional, auto-detect if not specified)"
    )

    args = parser.parse_args()

    Config.validate()
    Config.create_directories()

    # Check OSS configuration
    if not all([Config.OSS_ACCESS_KEY_ID, Config.OSS_ACCESS_KEY_SECRET, Config.OSS_BUCKET_NAME]):
        print("✗ Error: OSS configuration missing in .env file")
        print("  Required: OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME")
        exit(1)

    # Initialize OSS uploader
    oss_uploader = OSSUploader(
        access_key_id=Config.OSS_ACCESS_KEY_ID,
        access_key_secret=Config.OSS_ACCESS_KEY_SECRET,
        bucket_name=Config.OSS_BUCKET_NAME,
        endpoint=Config.OSS_ENDPOINT
    )

    # Initialize ASR processor
    processor = ParaformerASRProcessor(
        api_key=Config.DASHSCOPE_API_KEY,
        oss_uploader=oss_uploader,
        speaker_count=args.speakers
    )

    try:
        # Process file
        result = processor.process_video_file(Path(args.input_file))

        # Save result
        if args.output:
            output_path = Path(args.output)
        else:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Config.ASR_RESULTS_DIR / f"paraformer_asr_{timestamp}.json"

        processor.save_result(result, output_path)
        print(f"\n✓ Success! Result saved to: {output_path}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        exit(1)
