"""语音克隆管理器 - 处理MiniMax语音克隆流程"""
import requests
import json
import base64
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


class VoiceCloneManager:
    """管理语音克隆和克隆音色的TTS生成"""

    def __init__(self, api_key: str, group_id: str):
        """
        初始化语音克隆管理器

        Args:
            api_key: MiniMax API Key
            group_id: MiniMax Group ID
        """
        self.api_key = api_key
        self.group_id = group_id
        self.base_url = "https://api.minimax.chat"

    def upload_audio_file(self, audio_path: Path, purpose: str = "voice_clone") -> Optional[str]:
        """
        上传音频文件到MiniMax

        Args:
            audio_path: 音频文件路径
            purpose: 上传目的（默认: voice_clone）

        Returns:
            file_id (str) 或 None
        """
        url = f"{self.base_url}/v1/files/upload?GroupId={self.group_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()

        files = {
            "file": (audio_path.name, audio_bytes, "audio/mpeg")
        }
        data = {
            "purpose": purpose
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                base_resp = result.get('base_resp', {})

                if base_resp.get('status_code') == 0:
                    file_data = result.get('file', {})
                    file_id = file_data.get('file_id')

                    if file_id:
                        print(f"✓ 文件上传成功: {audio_path.name}")
                        print(f"✓ File ID: {file_id}")
                        return str(file_id)

            print(f"❌ 文件上传失败: {response.text}")
            return None

        except Exception as e:
            print(f"❌ 上传异常: {str(e)}")
            return None

    def clone_voice(
        self,
        audio_path: Path,
        voice_id: str,
        voice_name: str = "Cloned Voice"
    ) -> Optional[Dict[str, Any]]:
        """
        克隆音色

        Args:
            audio_path: 参考音频路径
            voice_id: 自定义voice_id (需以字母开头)
            voice_name: 音色名称

        Returns:
            包含voice_id和响应信息的字典，或None
        """
        # 步骤1: 上传音频文件
        print(f"\n{'='*60}")
        print(f"开始克隆音色: {voice_id}")
        print(f"{'='*60}")
        print(f"参考音频: {audio_path}")
        print(f"音频大小: {audio_path.stat().st_size / 1024:.1f}KB\n")

        file_id = self.upload_audio_file(audio_path)

        if not file_id:
            return None

        # 步骤2: 调用voice_clone API
        url = f"{self.base_url}/v1/voice_clone?GroupId={self.group_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "voice_id": voice_id,
            "file_id": int(file_id),  # 必须是int类型
            "voice_name": voice_name
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                result = response.json()
                base_resp = result.get('base_resp', {})

                if base_resp.get('status_code') == 0:
                    print(f"✅ 音色克隆成功!")
                    print(f"✓ Voice ID: {voice_id}")

                    clone_info = {
                        "voice_id": voice_id,
                        "voice_name": voice_name,
                        "file_id": file_id,
                        "source_audio": str(audio_path),
                        "response": result
                    }

                    return clone_info

            print(f"❌ 克隆失败: {response.text}")
            return None

        except Exception as e:
            print(f"❌ 克隆异常: {str(e)}")
            return None

    def generate_audio_with_cloned_voice(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        model: str = "speech-2.8-hd",
        speed: float = 1.0
    ) -> bool:
        """
        使用克隆的音色生成TTS音频

        Args:
            text: 要生成的文本
            voice_id: 克隆的voice_id
            output_path: 输出音频路径
            model: TTS模型名称
            speed: 语速 (默认1.0)

        Returns:
            是否成功
        """
        url = f"{self.base_url}/v1/t2a_v2?GroupId={self.group_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "text": text,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed
            },
            "audio_setting": {
                "format": "mp3",
                "sample_rate": 24000
            }
        }

        # 重试机制：处理 RPM 限流
        max_retries = 3
        rate_limit_wait = 65  # 限流等待时间

        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=90)

                if response.status_code == 200:
                    result = response.json()

                    # 检查是否触发限流
                    if 'base_resp' in result:
                        status_code = result['base_resp'].get('status_code', 0)
                        if status_code == 1002:  # rate limit exceeded
                            if attempt < max_retries:
                                print(f"⚠️  触发RPM限流 (尝试 {attempt + 1}/{max_retries + 1})")
                                print(f"⏳ 等待 {rate_limit_wait} 秒后重试...")
                                time.sleep(rate_limit_wait)
                                continue
                            else:
                                print(f"❌ 限流重试次数用尽")
                                return False

                    if 'data' in result and 'audio' in result['data']:
                        # MiniMax返回hex编码的音频
                        audio_hex = result['data']['audio']
                        audio_bytes = bytes.fromhex(audio_hex)

                        # 保存音频
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(audio_bytes)

                        print(f"✓ 音频生成成功: {output_path}")
                        print(f"✓ 文件大小: {len(audio_bytes) / 1024:.1f}KB")
                        return True

                print(f"❌ 生成失败: {response.text}")
                return False

            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                if attempt < max_retries:
                    wait_time = (2 ** (attempt + 1)) * 2
                    print(f"⚠️  网络错误 (尝试 {attempt + 1}/{max_retries + 1}): {type(e).__name__}")
                    print(f"⏳ 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 网络错误重试次数用尽: {str(e)}")
                    return False

            except Exception as e:
                print(f"❌ 生成异常: {str(e)}")
                return False

        return False

    def save_clone_info(self, clone_info: Dict[str, Any], output_file: Path):
        """
        保存克隆音色信息到JSON文件

        Args:
            clone_info: 克隆信息字典
            output_file: 输出文件路径
        """
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(clone_info, f, ensure_ascii=False, indent=2)

        print(f"✓ 克隆信息已保存: {output_file}")

    def load_clone_info(self, clone_info_file: Path) -> Optional[Dict[str, Any]]:
        """
        从JSON文件加载克隆音色信息

        Args:
            clone_info_file: 克隆信息文件路径

        Returns:
            克隆信息字典，或None
        """
        if not clone_info_file.exists():
            print(f"❌ 克隆信息文件不存在: {clone_info_file}")
            return None

        try:
            with open(clone_info_file, 'r') as f:
                clone_info = json.load(f)
            return clone_info

        except Exception as e:
            print(f"❌ 加载克隆信息失败: {str(e)}")
            return None

    def batch_clone_speakers(
        self,
        speaker_audios: Dict[str, Path],
        channel_id: str,
        channel_name: str = "Unknown"
    ) -> Dict[str, str]:
        """
        批量克隆多个speaker的音色

        Args:
            speaker_audios: speaker音频映射 {"speaker_0": Path, "speaker_1": Path}
            channel_id: YouTube频道ID，用于生成唯一voice_id
            channel_name: 频道名称

        Returns:
            音色映射 {"speaker_0": "voice_id_0", "speaker_1": "voice_id_1"}
        """
        print(f"\n{'='*60}")
        print(f"批量克隆音色 - 频道: {channel_name}")
        print(f"{'='*60}")
        print(f"Speaker数量: {len(speaker_audios)}")

        voice_mapping = {}
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        for speaker_id, audio_path in speaker_audios.items():
            # 生成唯一的voice_id: channel_speaker_timestamp
            voice_id = f"v_{channel_id[:8]}_{speaker_id}_{timestamp}"
            voice_name = f"{channel_name} - {speaker_id}"

            print(f"\n克隆 {speaker_id}...")
            clone_info = self.clone_voice(
                audio_path=audio_path,
                voice_id=voice_id,
                voice_name=voice_name
            )

            if clone_info:
                voice_mapping[speaker_id] = voice_id
                print(f"✅ {speaker_id} 克隆成功: {voice_id}")
            else:
                print(f"❌ {speaker_id} 克隆失败，将使用预设音色")
                # 克隆失败时使用预设音色
                voice_mapping[speaker_id] = self._get_fallback_voice(speaker_id)

            # 避免API限流
            time.sleep(1)

        print(f"\n{'='*60}")
        print(f"批量克隆完成: {len(voice_mapping)}/{len(speaker_audios)} 成功")
        print(f"{'='*60}")

        return voice_mapping

    def _get_fallback_voice(self, speaker_id: str) -> str:
        """
        获取预设的回退音色

        Args:
            speaker_id: speaker标识

        Returns:
            预设音色ID
        """
        fallback_voices = {
            "speaker_0": "Inspirational_girl",
            "speaker_1": "Deep_Voice_Man",
            "speaker_2": "Wise_Woman",
        }
        return fallback_voices.get(speaker_id, "Deep_Voice_Man")

    def test_voice_valid(self, voice_id: str) -> bool:
        """
        测试克隆音色是否仍然有效

        Args:
            voice_id: 要测试的voice_id

        Returns:
            是否有效
        """
        url = f"{self.base_url}/v1/t2a_v2?GroupId={self.group_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 用很短的测试文本
        payload = {
            "model": "speech-2.8-hd",
            "text": "测试",
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
                if 'data' in result and 'audio' in result['data']:
                    return True

            return False

        except Exception:
            return False

