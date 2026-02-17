"""YouTube video downloader using yt-dlp with cookie support"""
import subprocess
import sys
import os
import re
import json
from pathlib import Path
from typing import Optional


def extract_channel_id(url: str, proxy: Optional[str] = None) -> Optional[str]:
    """
    从YouTube URL提取频道ID

    Args:
        url: YouTube视频URL
        proxy: 代理URL

    Returns:
        频道ID (UC开头) 或 None
    """
    cmd = [
        "yt-dlp",
        url,
        "--dump-json",
        "--no-download",
        "--socket-timeout", "30",
    ]

    if proxy:
        cmd.extend(["--proxy", proxy])

    # 使用浏览器cookies
    cmd.extend(["--cookies-from-browser", "chrome"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            channel_id = info.get('channel_id')
            if channel_id:
                print(f"✓ 提取到频道ID: {channel_id}")
                return channel_id

            # 备选：从uploader_id提取
            uploader_id = info.get('uploader_id')
            if uploader_id and uploader_id.startswith('UC'):
                print(f"✓ 从uploader_id提取频道ID: {uploader_id}")
                return uploader_id

    except subprocess.TimeoutExpired:
        print("⚠️  提取频道ID超时")
    except json.JSONDecodeError:
        print("⚠️  解析频道信息失败")
    except Exception as e:
        print(f"⚠️  提取频道ID失败: {e}")

    return None


class YouTubeDownloader:
    def __init__(self, output_dir: Path, proxy: Optional[str] = None):
        """
        Initialize YouTube downloader

        Args:
            output_dir: Directory to save downloaded files
            proxy: Proxy URL (e.g., 'http://127.0.0.1:7897'). If None, will check HTTP_PROXY env var
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Use provided proxy or check environment variable
        self.proxy = proxy or os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY')
        if self.proxy:
            print(f"✓ YouTube Downloader will use proxy: {self.proxy}")

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
            "--remote-components", "ejs:github",  # Fix YouTube n-parameter challenge
            "-f", "bestvideo+bestaudio/best",  # Best quality video+audio
            "--merge-output-format", "mp4",    # Merge to mp4
            "-o", str(self.output_dir / (output_filename or "%(title)s.%(ext)s")),
            "--socket-timeout", "30",           # Socket timeout
            "--retries", "10",                  # Retry 10 times
            "--fragment-retries", "10",         # Fragment retry
            "--no-part",                        # Don't use .part files
            "--fixup", "detect_or_warn",        # Warn about fixup issues instead of failing
        ]

        # Add proxy if available
        if self.proxy:
            cmd.extend(["--proxy", self.proxy])

        # Use browser cookies - this is the most reliable method
        # Try Chrome first (most common)
        print("⚠️  直接从Chrome浏览器读取cookies（更可靠）")
        cmd.extend(["--cookies-from-browser", "chrome"])

        print(f"Downloading from: {url}")
        print(f"Output directory: {self.output_dir}")
        if self.proxy:
            print(f"Using proxy: {self.proxy}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)

            # Find the downloaded file
            if output_filename:
                # If output filename was specified, look for that specific file
                expected_file = self.output_dir / f"{output_filename}.mp4"

                if expected_file.exists():
                    downloaded_file = expected_file
                    print(f"✓ Downloaded: {downloaded_file}")
                    return downloaded_file
                else:
                    # Check if file exists without extension (yt-dlp fixup issue)
                    file_without_ext = self.output_dir / output_filename
                    if file_without_ext.exists():
                        print(f"⚠️  Found file without .mp4 extension: {file_without_ext}")
                        print(f"   Renaming to: {expected_file}")
                        file_without_ext.rename(expected_file)
                        downloaded_file = expected_file
                        print(f"✓ Downloaded and fixed: {downloaded_file}")
                        return downloaded_file

                    # Check for other possible extensions
                    possible_files = [
                        self.output_dir / f"{output_filename}.webm",
                        self.output_dir / f"{output_filename}.mkv",
                        self.output_dir / f"{output_filename}.mp4.part",
                    ]

                    for possible_file in possible_files:
                        if possible_file.exists():
                            print(f"⚠️  Found file with different extension: {possible_file}")
                            print(f"   Renaming to: {expected_file}")
                            possible_file.rename(expected_file)
                            downloaded_file = expected_file
                            print(f"✓ Downloaded and fixed: {downloaded_file}")
                            return downloaded_file

                    # File doesn't exist - download may have failed silently
                    raise RuntimeError(
                        f"Expected file not found: {expected_file}\n"
                        f"Download may have been skipped or failed. Please check yt-dlp output above."
                    )
            else:
                # If no filename specified, find the most recently created file
                downloaded_files = list(self.output_dir.glob("*.mp4"))
                if not downloaded_files:
                    raise RuntimeError("Download completed but no file found")
                downloaded_file = max(downloaded_files, key=lambda p: p.stat().st_mtime)
                print(f"✓ Downloaded: {downloaded_file}")
                return downloaded_file

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr

            # Provide helpful error messages
            if "SSL" in error_msg or "ssl" in error_msg:
                print("\n" + "="*80)
                print("❌ SSL 连接错误")
                print("="*80)
                print("这通常是网络问题。建议解决方法：")
                print("\n方法1: 检查代理设置")
                print("  确保 .env 文件中配置了正确的代理:")
                print("  HTTP_PROXY=http://127.0.0.1:7897")
                print("  HTTPS_PROXY=http://127.0.0.1:7897")
                print("\n方法2: 手动下载视频")
                print(f"  1. 手动下载视频到 {self.output_dir}")
                print(f"  2. 重命名为: {output_filename}.mp4")
                print("  3. 重新运行脚本")
                print("="*80 + "\n")

            print(f"Error during download: {error_msg}", file=sys.stderr)
            raise RuntimeError(f"Failed to download video: {error_msg}")

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
            "--remote-components", "ejs:github",  # Fix YouTube n-parameter challenge
            "-f", "bestaudio",
            "-x",  # Extract audio
            "--audio-format", "mp3",
            "-o", str(self.output_dir / (output_filename or "%(title)s.%(ext)s")),
            "--socket-timeout", "30",           # Socket timeout
            "--retries", "10",                  # Retry 10 times
            "--fragment-retries", "10",         # Fragment retry
        ]

        # Add proxy if available
        if self.proxy:
            cmd.extend(["--proxy", self.proxy])

        # Use browser cookies - this is the most reliable method
        print("⚠️  直接从Chrome浏览器读取cookies（更可靠）")
        cmd.extend(["--cookies-from-browser", "chrome"])

        print(f"Downloading audio from: {url}")
        print(f"Output directory: {self.output_dir}")
        if self.proxy:
            print(f"Using proxy: {self.proxy}")

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)

            # Find the downloaded file
            if output_filename:
                # If output filename was specified, look for that specific file
                expected_file = self.output_dir / f"{output_filename}.mp3"
                if expected_file.exists():
                    downloaded_file = expected_file
                    print(f"✓ Downloaded: {downloaded_file}")
                    return downloaded_file
                else:
                    raise RuntimeError(
                        f"Expected file not found: {expected_file}\n"
                        f"Download may have been skipped or failed. Please check yt-dlp output above."
                    )
            else:
                # If no filename specified, find the most recently created file
                downloaded_files = list(self.output_dir.glob("*.mp3"))
                if not downloaded_files:
                    raise RuntimeError("Download completed but no file found")
                downloaded_file = max(downloaded_files, key=lambda p: p.stat().st_mtime)
                print(f"✓ Downloaded: {downloaded_file}")
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
