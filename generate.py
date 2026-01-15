#!/usr/bin/env python3
"""
西经东译播客生成器 - 完整自动化流程

使用方法：
1. 编辑 start_prompt.md 文件，填入播客信息（包括YouTube URL）
2. 运行：python generate.py

完整流程：
- 自动下载视频（如果需要）
- 自动ASR转录（如果需要）
- 翻译 + TTS + 合并音频
- 生成播客描述文案
"""
import subprocess
import sys
import re
from pathlib import Path
from datetime import datetime
from config import Config
import json
from utils.podcast_manager import PodcastManager

def parse_start_prompt():
    """解析start_prompt.md文件"""
    start_prompt_file = Path("start_prompt.md")

    if not start_prompt_file.exists():
        print("❌ 错误：找不到 start_prompt.md 文件")
        print("\n请创建该文件并填入播客信息，格式如下：")
        print("=" * 80)
        print("播客名字是{...}，嘉宾是{...}")
        print("YouTube URL: https://www.youtube.com/watch?v=...")
        print("当前要转译的cookie文件目录地址：{...}")
        print("音色配置: speaker_0:{...}, speaker_1:{...}")
        print("=" * 80)
        sys.exit(1)

    with open(start_prompt_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取YouTube URL
    url_patterns = [
        r'YouTube URL[:：]\s*(https?://[^\s\n]+)',
        r'视频链接[:：]\s*(https?://[^\s\n]+)',
        r'URL[:：]\s*(https?://[^\s\n]+)',
    ]

    youtube_url = None
    for pattern in url_patterns:
        match = re.search(pattern, content)
        if match:
            youtube_url = match.group(1).strip()
            break

    # 提取cookie文件路径
    cookie_pattern = r'cookie文件目录地址[:：]\s*\{([^}]+)\}'
    cookie_match = re.search(cookie_pattern, content)
    cookie_path = cookie_match.group(1).strip() if cookie_match else None

    # 提取播客名
    podcast_pattern = r'播客名字是\{([^}]+)\}'
    podcast_match = re.search(podcast_pattern, content)
    podcast_name = podcast_match.group(1).strip() if podcast_match else None

    return {
        'youtube_url': youtube_url,
        'cookie_path': cookie_path,
        'podcast_name': podcast_name
    }

def check_podcast_exists(manager: PodcastManager, youtube_url: str, podcast_name: str):
    """检查播客是否已存在

    Args:
        manager: PodcastManager实例
        youtube_url: YouTube视频URL
        podcast_name: 播客名称

    Returns:
        podcast_id if exists, None otherwise
    """
    print("\n" + "=" * 80)
    print("🔍 检查播客是否已存在")
    print("=" * 80)
    print(f"目标播客: {podcast_name}")
    print(f"目标URL: {youtube_url}")
    print()

    podcast_id = manager.find_podcast_by_url(youtube_url)

    if podcast_id:
        metadata = manager.load_metadata(podcast_id)
        print("✅ 找到已存在的播客")
        print(f"  ID: {podcast_id}")
        print(f"  名称: {metadata.get('podcast_name')}")
        print(f"  创建时间: {metadata.get('created_at')}")

        # 检查文件状态
        has_video = manager.get_video_path(podcast_id).exists()
        has_asr = manager.get_asr_path(podcast_id).exists()

        print(f"\n文件状态:")
        print(f"  视频: {'✓' if has_video else '✗'}")
        print(f"  ASR: {'✓' if has_asr else '✗'}")
        print()

        return podcast_id

    print("❌ 未找到匹配的播客")
    print("  将创建新的播客")
    print()
    return None

def download_video(manager: PodcastManager, podcast_id: str, youtube_url: str, cookie_path: str):
    """下载YouTube视频到播客目录

    Args:
        manager: PodcastManager实例
        podcast_id: 播客ID
        youtube_url: YouTube URL
        cookie_path: Cookie文件路径

    Returns:
        视频文件路径
    """
    print("\n" + "=" * 80)
    print("📥 步骤1: 下载YouTube视频")
    print("=" * 80)
    print(f"URL: {youtube_url}")
    print(f"Cookie: {cookie_path}")

    from utils.youtube_downloader import YouTubeDownloader

    # 使用临时目录下载，然后移动到播客目录
    temp_dir = Path("output/temp_videos")
    temp_dir.mkdir(parents=True, exist_ok=True)
    downloader = YouTubeDownloader(temp_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    video_filename = f"video_{timestamp}"

    try:
        temp_video = downloader.download(
            url=youtube_url,
            cookie_file=cookie_path,
            output_filename=video_filename
        )

        # 移动到播客目录
        video_path = manager.get_video_path(podcast_id)
        temp_video.rename(video_path)

        print(f"✓ 视频下载成功: {video_path}")
        return video_path
    except Exception as e:
        print(f"❌ 视频下载失败: {e}")
        raise

def run_asr(manager: PodcastManager, podcast_id: str, video_file: Path):
    """运行ASR转录到播客目录

    Args:
        manager: PodcastManager实例
        podcast_id: 播客ID
        video_file: 视频文件路径

    Returns:
        ASR结果文件路径
    """
    print("\n" + "=" * 80)
    print("🎤 步骤2: ASR语音转录")
    print("=" * 80)
    print(f"处理文件: {video_file}")

    Config.validate()

    from utils.asr_processor import Qwen3ASRProcessor

    processor = Qwen3ASRProcessor(
        api_key=Config.DASHSCOPE_API_KEY,
        enable_diarization=True
    )

    try:
        result = processor.process_video_file(video_file)

        # 保存到播客目录
        asr_output = manager.get_asr_path(podcast_id)

        # 从metadata获取播客信息
        metadata = manager.load_metadata(podcast_id)

        processor.save_result(result, asr_output, metadata=metadata)

        print(f"✓ ASR转录完成: {asr_output}")
        return asr_output
    except Exception as e:
        print(f"❌ ASR转录失败: {e}")
        raise

def run_podcast_generation():
    """运行播客生成流程"""
    print("\n" + "=" * 80)
    print("🎙️ 步骤3: 生成完整播客")
    print("=" * 80)

    try:
        subprocess.run([sys.executable, "auto_generate_podcast.py"], check=True)
        print("✓ 播客生成完成")
    except subprocess.CalledProcessError as e:
        print(f"❌ 播客生成失败，错误代码: {e.returncode}")
        raise

def check_external_tools():
    """检查必需的外部工具"""
    import shutil

    missing_tools = []

    # 检查 ffmpeg
    if not shutil.which('ffmpeg'):
        missing_tools.append("ffmpeg - 音频处理工具")

    # 检查 yt-dlp（用于下载 YouTube 视频）
    if not shutil.which('yt-dlp'):
        missing_tools.append("yt-dlp - YouTube 视频下载工具")

    if missing_tools:
        print("❌ 错误：缺少必需的外部工具：")
        for tool in missing_tools:
            print(f"  - {tool}")
        print("\n安装方法（macOS）：")
        print("  brew install ffmpeg yt-dlp")
        print("\n其他系统请访问：")
        print("  - ffmpeg: https://ffmpeg.org/")
        print("  - yt-dlp: https://github.com/yt-dlp/yt-dlp")
        sys.exit(1)

def main():
    print("=" * 80)
    print("🎙️ 西经东译播客自动生成器 - 完整流程")
    print("=" * 80)
    print()

    # 检查外部工具
    check_external_tools()

    # 设置代理（用于下载YouTube视频）
    Config.setup_proxy()

    # 解析配置
    print("📋 解析配置文件...")
    config = parse_start_prompt()

    print(f"✓ 播客名称: {config['podcast_name']}")
    print(f"✓ YouTube URL: {config['youtube_url'] or '未提供'}")
    print(f"✓ Cookie文件: {config['cookie_path'] or '未提供'}")
    print()

    # 检查是否需要下载和ASR
    if not config['youtube_url']:
        print("\n❌ 错误：未在 start_prompt.md 中找到 YouTube URL")
        print("\n请在 start_prompt.md 中添加以下行：")
        print("YouTube URL: https://www.youtube.com/watch?v=...")
        sys.exit(1)

    # 初始化 PodcastManager
    manager = PodcastManager()

    # 检查播客是否已存在
    podcast_id = check_podcast_exists(manager, config['youtube_url'], config['podcast_name'])

    if podcast_id:
        # 播客已存在，检查是否需要重新下载或转录
        has_video = manager.get_video_path(podcast_id).exists()
        has_asr = manager.get_asr_path(podcast_id).exists()

        if has_video and has_asr:
            print("⏩ 视频和ASR已存在，跳过下载和转录步骤")
        else:
            if not has_video:
                print("\n需要下载视频")
                try:
                    download_video(manager, podcast_id, config['youtube_url'], config['cookie_path'])
                except Exception as e:
                    print(f"\n❌ 视频下载失败: {e}")
                    sys.exit(1)

            if not has_asr:
                print("\n需要进行ASR转录")
                video_path = manager.get_video_path(podcast_id)
                try:
                    run_asr(manager, podcast_id, video_path)
                except Exception as e:
                    print(f"\n❌ ASR转录失败: {e}")
                    sys.exit(1)
    else:
        # 创建新播客
        print("\n创建新的播客...")
        podcast_id = manager.create_podcast(
            youtube_url=config['youtube_url'],
            podcast_name=config['podcast_name'],
            cookie_path=config['cookie_path']
        )

        try:
            # 下载视频
            video_file = download_video(manager, podcast_id, config['youtube_url'], config['cookie_path'])

            # 运行ASR
            asr_file = run_asr(manager, podcast_id, video_file)

        except Exception as e:
            print(f"\n❌ 流程失败: {e}")
            sys.exit(1)

    # 运行播客生成（需要传递 podcast_id）
    try:
        run_podcast_generation()

        print("\n" + "=" * 80)
        print("✅ 完整播客生成成功！")
        print("=" * 80)

        # 显示播客信息
        manager.print_podcast_info(podcast_id)

    except Exception as e:
        print(f"\n❌ 播客生成失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
        sys.exit(1)
