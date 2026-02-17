"""音色库管理器 - 实现零维护的自动复用机制"""
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


class VoiceLibraryManager:
    """管理音色库，支持按频道ID索引和自动复用"""

    def __init__(
        self,
        library_path: str = "output/voice_library.json",
        api_key: Optional[str] = None,
        group_id: Optional[str] = None
    ):
        """
        初始化音色库管理器

        Args:
            library_path: 音色库JSON文件路径
            api_key: MiniMax API Key（用于音色有效性检测）
            group_id: MiniMax Group ID（用于音色有效性检测）
        """
        self.library_path = Path(library_path)
        self.api_key = api_key
        self.group_id = group_id
        self.base_url = "https://api.minimax.chat"
        self._library: Dict[str, Dict[str, Any]] = {}

    def load_library(self) -> Dict[str, Dict[str, Any]]:
        """
        加载音色库，不存在则创建空库

        Returns:
            音色库字典
        """
        if self.library_path.exists():
            try:
                with open(self.library_path, 'r', encoding='utf-8') as f:
                    self._library = json.load(f)
                print(f"✓ 音色库加载成功: {self.library_path}")
                print(f"✓ 已有 {len(self._library)} 个频道音色")
            except Exception as e:
                print(f"⚠ 音色库加载失败，创建空库: {str(e)}")
                self._library = {}
        else:
            print(f"✓ 音色库不存在，创建空库: {self.library_path}")
            self._library = {}
            # 确保目录存在
            self.library_path.parent.mkdir(parents=True, exist_ok=True)

        return self._library

    def save_library(self) -> bool:
        """
        保存音色库到文件

        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            self.library_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.library_path, 'w', encoding='utf-8') as f:
                json.dump(self._library, f, ensure_ascii=False, indent=2)

            print(f"✓ 音色库保存成功: {self.library_path}")
            return True

        except Exception as e:
            print(f"❌ 音色库保存失败: {str(e)}")
            return False

    def get_voice(self, channel_id: str) -> Optional[str]:
        """
        查询指定频道的音色

        Args:
            channel_id: YouTube频道ID（如 UC_channelid123）

        Returns:
            voice_id 或 None（未找到）
        """
        if channel_id in self._library:
            voice_info = self._library[channel_id]
            voice_id = voice_info.get("host_voice_id")

            if voice_id:
                channel_name = voice_info.get("channel_name", "Unknown")
                print(f"✓ 找到频道音色: {channel_name}")
                print(f"✓ Voice ID: {voice_id}")
                return voice_id

        print(f"✗ 未找到频道音色: {channel_id}")
        return None

    def save_voice(
        self,
        channel_id: str,
        channel_name: str,
        voice_id: str
    ) -> bool:
        """
        保存新克隆的音色到音色库

        Args:
            channel_id: YouTube频道ID
            channel_name: 频道名称
            voice_id: 克隆的voice_id

        Returns:
            是否保存成功
        """
        now = datetime.now().isoformat()

        self._library[channel_id] = {
            "channel_name": channel_name,
            "host_voice_id": voice_id,
            "created_at": now,
            "last_used": now
        }

        print(f"✓ 音色已添加到库: {channel_name}")
        print(f"✓ Channel ID: {channel_id}")
        print(f"✓ Voice ID: {voice_id}")

        return self.save_library()

    def update_last_used(self, channel_id: str) -> bool:
        """
        更新指定频道音色的最后使用时间

        Args:
            channel_id: YouTube频道ID

        Returns:
            是否更新成功
        """
        if channel_id not in self._library:
            print(f"⚠ 频道不存在于音色库: {channel_id}")
            return False

        self._library[channel_id]["last_used"] = datetime.now().isoformat()
        print(f"✓ 更新最后使用时间: {channel_id}")

        return self.save_library()

    def is_voice_valid(self, voice_id: str) -> bool:
        """
        检测音色是否有效（调用MiniMax API测试）

        Args:
            voice_id: 要检测的voice_id

        Returns:
            音色是否有效
        """
        if not self.api_key or not self.group_id:
            print("⚠ 未配置API Key或Group ID，跳过音色有效性检测")
            return True  # 无法检测时默认有效

        url = f"{self.base_url}/v1/t2a_v2?GroupId={self.group_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 使用简短测试文本
        payload = {
            "model": "speech-2.8-hd",
            "text": "Test.",
            "voice_setting": {
                "voice_id": voice_id,
                "speed": 1.0
            },
            "audio_setting": {
                "format": "mp3",
                "sample_rate": 24000
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                base_resp = result.get('base_resp', {})

                if base_resp.get('status_code') == 0:
                    print(f"✓ 音色有效: {voice_id}")
                    return True

            print(f"✗ 音色无效或已过期: {voice_id}")
            return False

        except Exception as e:
            print(f"⚠ 音色检测异常: {str(e)}")
            return True  # 网络异常时默认有效，避免误删

    def get_or_clone_voice(
        self,
        channel_id: str,
        channel_name: str,
        clone_callback: Optional[callable] = None
    ) -> Optional[str]:
        """
        获取频道音色，如不存在则触发克隆回调

        Args:
            channel_id: YouTube频道ID
            channel_name: 频道名称
            clone_callback: 克隆回调函数，返回新的voice_id

        Returns:
            voice_id 或 None
        """
        # 先尝试从库中获取
        voice_id = self.get_voice(channel_id)

        if voice_id:
            # 检测音色是否有效
            if self.is_voice_valid(voice_id):
                self.update_last_used(channel_id)
                return voice_id
            else:
                print(f"⚠ 音色已失效，需要重新克隆: {voice_id}")

        # 需要克隆新音色
        if clone_callback:
            print(f"\n{'='*60}")
            print(f"开始为频道克隆音色: {channel_name}")
            print(f"{'='*60}")

            new_voice_id = clone_callback()

            if new_voice_id:
                self.save_voice(channel_id, channel_name, new_voice_id)
                return new_voice_id

        return None

    def list_voices(self) -> Dict[str, Dict[str, Any]]:
        """
        列出所有已保存的音色

        Returns:
            音色库字典
        """
        print(f"\n{'='*60}")
        print(f"音色库列表 (共 {len(self._library)} 个)")
        print(f"{'='*60}")

        for channel_id, info in self._library.items():
            print(f"\n频道: {info.get('channel_name', 'Unknown')}")
            print(f"  Channel ID: {channel_id}")
            print(f"  Voice ID: {info.get('host_voice_id', 'N/A')}")
            print(f"  创建时间: {info.get('created_at', 'N/A')}")
            print(f"  最后使用: {info.get('last_used', 'N/A')}")

        return self._library

    def remove_voice(self, channel_id: str) -> bool:
        """
        从音色库中移除指定频道的音色

        Args:
            channel_id: YouTube频道ID

        Returns:
            是否移除成功
        """
        if channel_id not in self._library:
            print(f"⚠ 频道不存在于音色库: {channel_id}")
            return False

        channel_name = self._library[channel_id].get("channel_name", "Unknown")
        del self._library[channel_id]

        print(f"✓ 已移除频道音色: {channel_name}")

        return self.save_library()
