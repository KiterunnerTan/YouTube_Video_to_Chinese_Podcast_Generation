"""YouTube video downloader using yt-dlp with cookie support"""
import subprocess
import sys
from pathlib import Path
from typing import Optional


class YouTubeDownloader:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download(
        self,
        url: str,
        cookie_file: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> Path:
        """
        Download video/audio from YouTube URL

        Args:
            url: YouTube video URL
            cookie_file: Path to cookies.txt file (from "Get cookies.txt LOCALLY" extension)
            output_filename: Optional custom output filename (without extension)

        Returns:
            Path to the downloaded file

        Raises:
            RuntimeError: If download fails
        """
        # Base command
        cmd = [
            "yt-dlp",
            url,
            "-f", "bestvideo+bestaudio/best",  # Best quality video+audio
            "--merge-output-format", "mp4",    # Merge to mp4
            "-o", str(self.output_dir / (output_filename or "%(title)s.%(ext)s")),
        ]

        # Add cookie file if provided
        if cookie_file:
            cookie_path = Path(cookie_file)
            if not cookie_path.exists():
                raise FileNotFoundError(f"Cookie file not found: {cookie_file}")
            cmd.extend(["--cookies", str(cookie_path)])

        print(f"Downloading from: {url}")
        print(f"Output directory: {self.output_dir}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)

            # Find the downloaded file
            downloaded_files = list(self.output_dir.glob("*.mp4"))
            if not downloaded_files:
                raise RuntimeError("Download completed but no file found")

            # Return the most recently created file
            downloaded_file = max(downloaded_files, key=lambda p: p.stat().st_mtime)
            print(f"Downloaded: {downloaded_file}")
            return downloaded_file

        except subprocess.CalledProcessError as e:
            print(f"Error during download: {e.stderr}", file=sys.stderr)
            raise RuntimeError(f"Failed to download video: {e.stderr}")

    def download_audio_only(
        self,
        url: str,
        cookie_file: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> Path:
        """
        Download audio only from YouTube URL

        Args:
            url: YouTube video URL
            cookie_file: Path to cookies.txt file
            output_filename: Optional custom output filename (without extension)

        Returns:
            Path to the downloaded audio file

        Raises:
            RuntimeError: If download fails
        """
        cmd = [
            "yt-dlp",
            url,
            "-f", "bestaudio",
            "-x",  # Extract audio
            "--audio-format", "mp3",
            "-o", str(self.output_dir / (output_filename or "%(title)s.%(ext)s")),
        ]

        if cookie_file:
            cookie_path = Path(cookie_file)
            if not cookie_path.exists():
                raise FileNotFoundError(f"Cookie file not found: {cookie_file}")
            cmd.extend(["--cookies", str(cookie_path)])

        print(f"Downloading audio from: {url}")
        print(f"Output directory: {self.output_dir}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)

            # Find the downloaded file
            downloaded_files = list(self.output_dir.glob("*.mp3"))
            if not downloaded_files:
                raise RuntimeError("Download completed but no file found")

            downloaded_file = max(downloaded_files, key=lambda p: p.stat().st_mtime)
            print(f"Downloaded: {downloaded_file}")
            return downloaded_file

        except subprocess.CalledProcessError as e:
            print(f"Error during download: {e.stderr}", file=sys.stderr)
            raise RuntimeError(f"Failed to download audio: {e.stderr}")


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description="Download YouTube videos with cookie support")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("-c", "--cookie", help="Path to cookies.txt file")
    parser.add_argument("-o", "--output", help="Output directory", default="./downloads")
    parser.add_argument("-a", "--audio-only", action="store_true", help="Download audio only")
    parser.add_argument("-n", "--filename", help="Output filename (without extension)")

    args = parser.parse_args()

    downloader = YouTubeDownloader(Path(args.output))

    try:
        if args.audio_only:
            file_path = downloader.download_audio_only(
                args.url,
                cookie_file=args.cookie,
                output_filename=args.filename
            )
        else:
            file_path = downloader.download(
                args.url,
                cookie_file=args.cookie,
                output_filename=args.filename
            )
        print(f"\nSuccess! File saved to: {file_path}")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
