"""播客文件管理系统 - 使用唯一标识符管理每个播客的所有文件"""
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class PodcastManager:
    """
    播客文件管理器 - 为每个播客创建独立目录，避免文件混淆

    目录结构:
    output/
      podcasts/
        {podcast_id}/
          metadata.json       # 播客信息（名称、URL、创建时间等）
          video.mp4           # 下载的视频
          asr.json            # ASR转录结果
          asr_processed.json  # 处理后的ASR结果
          translation.json    # 翻译结果
          audio_segments/     # 音频片段
            segment_0000.mp3
            segment_0001.mp3
          final.mp3           # 最终音频
          description.txt     # 节目描述
          summary.txt         # 节目概要
    """

    def __init__(self, base_dir: Path = Path("output/podcasts")):
        """
        初始化播客管理器

        Args:
            base_dir: 播客存储根目录
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_podcast_id(youtube_url: str) -> str:
        """
        基于YouTube URL生成唯一的播客ID

        Args:
            youtube_url: YouTube视频URL

        Returns:
            12位十六进制字符串作为唯一ID
        """
        return hashlib.md5(youtube_url.encode()).hexdigest()[:12]

    def get_podcast_dir(self, podcast_id: str) -> Path:
        """获取播客目录"""
        podcast_dir = self.base_dir / podcast_id
        podcast_dir.mkdir(parents=True, exist_ok=True)
        return podcast_dir

    def create_podcast(
        self,
        youtube_url: str,
        podcast_name: str,
        **extra_metadata
    ) -> str:
        """
        创建新的播客（初始化目录和metadata）

        Args:
            youtube_url: YouTube视频URL
            podcast_name: 播客名称
            **extra_metadata: 额外的元数据（如嘉宾名、cookie文件路径等）

        Returns:
            podcast_id
        """
        podcast_id = self.generate_podcast_id(youtube_url)
        podcast_dir = self.get_podcast_dir(podcast_id)

        # 创建metadata
        metadata = {
            "podcast_id": podcast_id,
            "podcast_name": podcast_name,
            "youtube_url": youtube_url,
            "created_at": datetime.now().isoformat(),
            **extra_metadata
        }

        # 保存metadata
        self.save_metadata(podcast_id, metadata)

        print(f"✓ 播客已创建: {podcast_name}")
        print(f"  ID: {podcast_id}")
        print(f"  目录: {podcast_dir}")

        return podcast_id

    def save_metadata(self, podcast_id: str, metadata: Dict[str, Any]):
        """保存播客元数据"""
        podcast_dir = self.get_podcast_dir(podcast_id)
        metadata_file = podcast_dir / "metadata.json"

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def load_metadata(self, podcast_id: str) -> Optional[Dict[str, Any]]:
        """加载播客元数据"""
        metadata_file = self.get_podcast_dir(podcast_id) / "metadata.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def update_metadata(self, podcast_id: str, **updates):
        """更新播客元数据"""
        metadata = self.load_metadata(podcast_id) or {}
        metadata.update(updates)
        metadata["updated_at"] = datetime.now().isoformat()
        self.save_metadata(podcast_id, metadata)

    # ========================================================================
    # 文件路径获取方法
    # ========================================================================

    def get_video_path(self, podcast_id: str) -> Path:
        """获取视频文件路径"""
        return self.get_podcast_dir(podcast_id) / "video.mp4"

    def get_asr_path(self, podcast_id: str, processed: bool = False) -> Path:
        """获取ASR结果文件路径"""
        filename = "asr_processed.json" if processed else "asr.json"
        return self.get_podcast_dir(podcast_id) / filename

    def get_translation_path(self, podcast_id: str) -> Path:
        """获取翻译结果文件路径"""
        return self.get_podcast_dir(podcast_id) / "translation.json"

    def get_audio_segments_dir(self, podcast_id: str) -> Path:
        """获取音频片段目录"""
        segments_dir = self.get_podcast_dir(podcast_id) / "audio_segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        return segments_dir

    def get_final_audio_path(self, podcast_id: str) -> Path:
        """获取最终音频文件路径"""
        return self.get_podcast_dir(podcast_id) / "final.mp3"

    def get_description_path(self, podcast_id: str) -> Path:
        """获取节目描述文件路径"""
        return self.get_podcast_dir(podcast_id) / "description.txt"

    def get_summary_path(self, podcast_id: str) -> Path:
        """获取节目概要文件路径"""
        return self.get_podcast_dir(podcast_id) / "summary.txt"

    def get_prologue_path(self, podcast_id: str, raw: bool = False) -> Path:
        """获取开场白音频路径"""
        filename = "prologue_raw.mp3" if raw else "prologue_final.mp3"
        return self.get_podcast_dir(podcast_id) / filename

    def get_summary_audio_path(self, podcast_id: str, raw: bool = False) -> Path:
        """获取概要音频路径"""
        filename = "summary_raw.mp3" if raw else "summary_final.mp3"
        return self.get_podcast_dir(podcast_id) / filename

    # ========================================================================
    # 播客查询和管理方法
    # ========================================================================

    def list_podcasts(self, limit: int = 10) -> list:
        """
        列出所有播客（按创建时间倒序）

        Args:
            limit: 返回的最大数量

        Returns:
            播客元数据列表
        """
        podcasts = []

        for podcast_dir in self.base_dir.iterdir():
            if podcast_dir.is_dir():
                metadata = self.load_metadata(podcast_dir.name)
                if metadata:
                    podcasts.append(metadata)

        # 按创建时间倒序排序
        podcasts.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return podcasts[:limit]

    def find_podcast_by_url(self, youtube_url: str) -> Optional[str]:
        """
        根据YouTube URL查找播客ID

        Args:
            youtube_url: YouTube视频URL

        Returns:
            podcast_id 或 None
        """
        podcast_id = self.generate_podcast_id(youtube_url)
        podcast_dir = self.get_podcast_dir(podcast_id)

        if (podcast_dir / "metadata.json").exists():
            return podcast_id
        return None

    def delete_podcast(self, podcast_id: str):
        """删除播客（包括所有文件）"""
        import shutil
        podcast_dir = self.get_podcast_dir(podcast_id)

        if podcast_dir.exists():
            metadata = self.load_metadata(podcast_id)
            podcast_name = metadata.get('podcast_name', 'Unknown') if metadata else 'Unknown'

            shutil.rmtree(podcast_dir)
            print(f"✓ 已删除播客: {podcast_name} ({podcast_id})")
        else:
            print(f"⚠️  播客不存在: {podcast_id}")

    def cleanup_old_podcasts(self, keep_recent: int = 5):
        """
        清理旧的播客，保留最近的N个

        Args:
            keep_recent: 保留的播客数量
        """
        podcasts = self.list_podcasts(limit=9999)

        if len(podcasts) <= keep_recent:
            print(f"✓ 当前有 {len(podcasts)} 个播客，无需清理")
            return

        to_delete = podcasts[keep_recent:]
        print(f"🗑️  清理 {len(to_delete)} 个旧播客...")

        for podcast in to_delete:
            self.delete_podcast(podcast['podcast_id'])

        print(f"✓ 清理完成，保留了最近 {keep_recent} 个播客")

    def print_podcast_info(self, podcast_id: str):
        """打印播客信息"""
        metadata = self.load_metadata(podcast_id)

        if not metadata:
            print(f"❌ 播客不存在: {podcast_id}")
            return

        print("\n" + "=" * 80)
        print(f"📻 播客信息")
        print("=" * 80)
        print(f"ID: {metadata.get('podcast_id')}")
        print(f"名称: {metadata.get('podcast_name')}")
        print(f"URL: {metadata.get('youtube_url')}")
        print(f"创建时间: {metadata.get('created_at')}")
        if 'updated_at' in metadata:
            print(f"更新时间: {metadata.get('updated_at')}")

        # 显示文件状态
        podcast_dir = self.get_podcast_dir(podcast_id)
        print(f"\n文件状态:")
        files = {
            "视频": self.get_video_path(podcast_id),
            "ASR结果": self.get_asr_path(podcast_id),
            "翻译结果": self.get_translation_path(podcast_id),
            "最终音频": self.get_final_audio_path(podcast_id),
            "节目描述": self.get_description_path(podcast_id),
        }

        for name, path in files.items():
            status = "✓" if path.exists() else "✗"
            size = f"({path.stat().st_size / 1024 / 1024:.1f}MB)" if path.exists() else ""
            print(f"  {status} {name}: {path.name} {size}")

        print("=" * 80 + "\n")


if __name__ == "__main__":
    # 测试代码
    manager = PodcastManager()

    # 创建测试播客
    test_url = "https://www.youtube.com/watch?v=test123"
    podcast_id = manager.create_podcast(
        youtube_url=test_url,
        podcast_name="测试播客",
        guest_name="测试嘉宾"
    )

    # 打印信息
    manager.print_podcast_info(podcast_id)

    # 列出所有播客
    print("所有播客:")
    for podcast in manager.list_podcasts():
        print(f"  - {podcast['podcast_name']} ({podcast['podcast_id']})")
