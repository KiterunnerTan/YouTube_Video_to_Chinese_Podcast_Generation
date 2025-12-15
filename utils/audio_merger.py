"""Audio merging module to combine segment audio files"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any


class AudioMerger:
    def __init__(self):
        """Initialize audio merger"""
        pass

    def merge_audio_files(
        self,
        audio_files: List[str],
        output_path: Path,
        format: str = "mp3"
    ) -> Path:
        """
        Merge multiple audio files into one using ffmpeg

        Args:
            audio_files: List of audio file paths (in order)
            output_path: Path to save merged audio
            format: Output format (mp3, wav, etc.)

        Returns:
            Path to merged audio file

        Raises:
            RuntimeError: If merging fails
        """
        if not audio_files:
            raise ValueError("No audio files to merge")

        print(f"Merging {len(audio_files)} audio files using ffmpeg...")

        try:
            # Create output directory
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Create a temporary file list for ffmpeg
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                filelist_path = f.name
                for audio_file in audio_files:
                    # ffmpeg concat demuxer requires this format
                    f.write(f"file '{Path(audio_file).absolute()}'\n")
                    print(f"Adding: {Path(audio_file).name}")

            # Use ffmpeg to concatenate
            # Use re-encoding instead of copy to fix potential metadata issues
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-ar', '24000',  # Set sample rate to 24kHz (common for TTS)
                '-ac', '1',  # Mono audio
                '-b:a', '128k',  # Bitrate
                '-y',  # Overwrite output file
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Clean up temp file
            Path(filelist_path).unlink()

            print(f"Merged audio saved to: {output_path}")

            # Get duration using ffprobe
            duration_info = self.get_audio_info(output_path)
            if duration_info:
                duration_sec = duration_info.get('duration_seconds', 0)
                print(f"Total duration: {duration_sec:.2f} seconds ({duration_sec/60:.2f} minutes)")

            return output_path

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to merge audio files with ffmpeg: {e.stderr}")
        except Exception as e:
            raise RuntimeError(f"Failed to merge audio files: {str(e)}")

    def merge_from_manifest(
        self,
        manifest_path: Path,
        output_path: Path,
        format: str = "mp3"
    ) -> Path:
        """
        Merge audio files from a manifest JSON

        Args:
            manifest_path: Path to audio manifest JSON file
            output_path: Path to save merged audio
            format: Output format

        Returns:
            Path to merged audio file
        """
        print(f"Loading manifest from: {manifest_path}")

        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        audio_segments = data.get("audio_segments", [])

        if not audio_segments:
            raise ValueError("No audio segments found in manifest")

        # Sort by segment_id to ensure correct order
        audio_segments.sort(key=lambda x: x.get("segment_id", 0))

        # Extract audio file paths
        audio_files = [seg["audio_file"] for seg in audio_segments]

        # Verify all files exist
        missing_files = [f for f in audio_files if not Path(f).exists()]
        if missing_files:
            raise FileNotFoundError(
                f"Missing audio files: {', '.join(missing_files)}"
            )

        # Merge
        return self.merge_audio_files(audio_files, output_path, format)

    def get_audio_info(self, audio_path: Path) -> Dict[str, Any]:
        """
        Get information about an audio file using ffprobe

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with audio information
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(audio_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            info = json.loads(result.stdout)
            format_info = info.get('format', {})

            duration = float(format_info.get('duration', 0))

            return {
                "duration_seconds": duration,
                "duration_ms": int(duration * 1000),
                "bit_rate": format_info.get('bit_rate', 'unknown'),
                "format_name": format_info.get('format_name', 'unknown'),
                "size": format_info.get('size', 'unknown')
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get audio info: {str(e)}")


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description="Merge audio segments")
    parser.add_argument(
        "manifest",
        help="Path to audio manifest JSON file"
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output audio file path"
    )
    parser.add_argument(
        "-f", "--format",
        default="mp3",
        help="Output format (default: mp3)"
    )

    args = parser.parse_args()

    merger = AudioMerger()

    try:
        output_path = merger.merge_from_manifest(
            Path(args.manifest),
            Path(args.output),
            format=args.format
        )

        # Show info about merged audio
        info = merger.get_audio_info(output_path)
        print("\nAudio Information:")
        for key, value in info.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
