"""Gemini TTS generator v1.4 with multi-speaker voice support"""
import json
import time
import os
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from .audio_cache import AudioCache
from .proxy_health_checker import ProxyHealthChecker


class VoiceManager:
    """
    音色管理器 - 支持多speaker自动分配音色
    MiniMax音色方案: 专业权威型
    """
    # MiniMax音色映射（2-speaker播客方案 - 默认）
    DEFAULT_VOICE_QUEUE = [
        ("speaker_0", "Inspirational_girl"),  # 鼓舞人心的声音 - 热情、有感染力
        ("speaker_1", "Deep_Voice_Man"),      # 深沉男性 - 权威、稳重
    ]

    def __init__(self, voice_config: Optional[Dict[str, str]] = None):
        """
        初始化音色管理器

        Args:
            voice_config: 自定义音色配置，如 {"speaker_0": "Grounded_Grace", "speaker_1": "Credible_Alex"}
                         如果不传，使用默认配置
        """
        if voice_config:
            self.voice_mapping = voice_config
            print(f"✓ 使用自定义音色配置: {voice_config}")
        else:
            self.voice_mapping = dict(self.DEFAULT_VOICE_QUEUE)
            print(f"✓ 使用默认音色配置")

    def get_voice(self, speaker_id: int) -> str:
        """
        获取指定speaker的音色

        Args:
            speaker_id: speaker编号（0, 1, 2...）

        Returns:
            音色名称
        """
        speaker_name = f"speaker_{speaker_id}"

        # 如果有配置，返回配置的音色
        if speaker_name in self.voice_mapping:
            return self.voice_mapping[speaker_name]

        # 如果超出范围，循环复用已有的音色配置
        # 获取所有已配置的speaker，按编号排序
        configured_speakers = sorted(self.voice_mapping.keys())
        if not configured_speakers:
            raise ValueError("No voice configuration available")

        # 循环复用：超出范围的speaker使用已有配置（取模）
        fallback_index = speaker_id % len(configured_speakers)
        fallback_speaker = configured_speakers[fallback_index]
        print(f"  ℹ️  {speaker_name} 未配置，复用 {fallback_speaker} 的音色")
        return self.voice_mapping[fallback_speaker]

    def get_all_speakers_from_text(self, text: str) -> List[str]:
        """
        从文本中提取所有speaker

        Args:
            text: 包含speaker标记的文本

        Returns:
            speaker列表，如 ["speaker_0", "speaker_1"]
        """
        import re
        pattern = r'^(speaker_\d+):'
        speakers = set()

        for line in text.split('\n'):
            match = re.match(pattern, line.strip())
            if match:
                speakers.add(match.group(1))

        return sorted(list(speakers))

    def build_multi_speaker_config(self, text: str) -> Dict[str, Any]:
        """
        根据文本中的speaker构建multiSpeakerVoiceConfig

        ⚠️ 要求: 文本中必须只有speaker_0和speaker_1 (翻译时控制)

        Args:
            text: 包含speaker标记的文本 (只有speaker_0和speaker_1)

        Returns:
            speechConfig配置
        """
        speakers = self.get_all_speakers_from_text(text)

        if not speakers:
            raise ValueError("No speakers found in text")

        # ⚠️ Gemini TTS API硬性限制: 必须恰好2个speaker
        if len(speakers) > 2:
            raise ValueError(
                f"Text has {len(speakers)} speakers: {speakers}. "
                f"Gemini TTS only supports exactly 2 speakers. "
                f"Please ensure translation uses only speaker_0 and speaker_1."
            )

        # 如果只有1个speaker,自动补充第二个
        if len(speakers) == 1:
            if "speaker_0" in speakers:
                speakers.append("speaker_1")
            else:
                speakers.insert(0, "speaker_0")

        # 构建speaker voice配置 (恰好2个: Kore女声 + Charon男声)
        speaker_voice_configs = [
            {
                "speaker": "speaker_0",
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": "Kore"  # 女声
                    }
                }
            },
            {
                "speaker": "speaker_1",
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": "Charon"  # 男声
                    }
                }
            }
        ]

        return {
            "multiSpeakerVoiceConfig": {
                "speakerVoiceConfigs": speaker_voice_configs
            }
        }


class GeminiTTSGeneratorV14:
    # RPM 限制配置
    RPM_LIMIT = 20  # MiniMax API 每分钟请求限制
    REQUEST_INTERVAL = 3.0  # 每次请求后等待秒数 (60/20=3)
    RATE_LIMIT_WAIT = 65  # 遇到限流时等待秒数

    def __init__(
        self,
        api_key: str,
        group_id: str,
        model_name: str = "speech-2.8-hd",
        voice_manager: Optional[VoiceManager] = None,
        enable_cache: bool = True
    ):
        """
        Initialize MiniMax TTS generator (v1.4 compatible interface)

        Args:
            api_key: MiniMax API key
            group_id: MiniMax Group ID
            model_name: TTS model name
            voice_manager: 音色管理器（可选，默认创建新的）
            enable_cache: Enable request caching to reduce API calls
        """
        self.api_key = api_key
        self.group_id = group_id
        self.model_name = model_name
        self.base_url = "https://api.minimax.chat"
        self.voice_manager = voice_manager or VoiceManager()
        self.cache = AudioCache() if enable_cache else None

        print(f"✓ Using MiniMax TTS model: {model_name}")
        print(f"✓ Voice mapping: speaker_0={self.voice_manager.voice_mapping.get('speaker_0')}, "
              f"speaker_1={self.voice_manager.voice_mapping.get('speaker_1')}")
        print(f"✓ Rate limit: {self.RPM_LIMIT} RPM, interval={self.REQUEST_INTERVAL}s")
        if self.cache:
            print(f"✓ Request caching enabled")

    def _parse_speaker_segments(self, text: str) -> List[Dict[str, Any]]:
        """
        解析多speaker文本为独立segments

        Args:
            text: 包含speaker标记的文本，如 "speaker_0: hello\nspeaker_1: world"

        Returns:
            List of segments: [{"speaker": "speaker_0", "content": "hello", "voice_id": "Wise_Woman"}, ...]
        """
        import re

        segments = []
        pattern = r'^(speaker_\d+):\s*(.+)$'

        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue

            match = re.match(pattern, line)
            if match:
                speaker_id, content = match.groups()
                voice_id = self.voice_manager.get_voice(int(speaker_id.split('_')[1]))
                segments.append({
                    "speaker": speaker_id,
                    "content": content.strip(),
                    "voice_id": voice_id
                })
            else:
                # 如果没有speaker标记，追加到上一个segment
                if segments:
                    segments[-1]["content"] += " " + line

        return segments

    def generate_audio(
        self,
        text: str,
        output_path: Path,
        language: str = "zh-CN"
    ) -> Path:
        """
        Generate audio from text with multi-speaker support using MiniMax API

        Args:
            text: Text with speaker markers (e.g., "speaker_0: hello\nspeaker_1: world")
            output_path: Path to save audio file
            language: Language code (not used in MiniMax)

        Returns:
            Path to generated audio file
        """
        # Check cache first
        cache_key = f"{text}_{self.model_name}"
        if self.cache:
            cached_audio = self.cache.get(text, self.model_name, {"model": self.model_name})
            if cached_audio:
                import shutil
                import os
                output_path.parent.mkdir(parents=True, exist_ok=True)
                # Only copy if source and destination are different files
                try:
                    if os.path.samefile(cached_audio, output_path):
                        print(f"✓ Using cached audio (already at target): {output_path}")
                    else:
                        shutil.copy(cached_audio, output_path)
                        print(f"✓ Using cached audio: {output_path}")
                except (OSError, FileNotFoundError):
                    # If files don't exist or can't be compared, just copy
                    shutil.copy(cached_audio, output_path)
                    print(f"✓ Using cached audio: {output_path}")
                return output_path

        # 解析speaker segments
        segments = self._parse_speaker_segments(text)

        # 打印使用的音色配置
        speakers = self.voice_manager.get_all_speakers_from_text(text)
        print(f"📻 Speakers detected: {len(speakers)}")
        for speaker_name in speakers:
            voice_id = self.voice_manager.get_voice(int(speaker_name.split('_')[1]))
            print(f"   {speaker_name}: {voice_id}")

        print(f"Generating audio ({len(segments)} segments, {len(text)} chars total)...")

        # 为每个segment生成音频
        audio_chunks = []
        for i, segment in enumerate(segments):
            url = f"{self.base_url}/v1/t2a_v2?GroupId={self.group_id}"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model_name,
                "text": segment["content"],
                "voice_setting": {
                    "voice_id": segment["voice_id"],
                    "speed": 1.0
                    # 不传emotion参数，让API自动推断情绪（类似Gemini 2.5 Pro）
                },
                "audio_setting": {
                    "format": "mp3",
                    "sample_rate": 24000
                }
            }

            # DEBUG: 打印实际发送的voice_id
            print(f"  Segment {i+1}/{len(segments)}: speaker={segment.get('speaker')}, voice_id={segment['voice_id']}")

            # 重试机制：最多3次重试
            max_retries = 3
            retry_count = 0
            success = False

            while retry_count <= max_retries and not success:
                try:
                    # 增加超时时间到90秒
                    response = requests.post(url, headers=headers, json=payload, timeout=90)

                    if response.status_code != 200:
                        raise RuntimeError(f"MiniMax API error: {response.status_code} - {response.text}")

                    result = response.json()

                    # 检查是否触发限流
                    if "base_resp" in result:
                        status_code = result["base_resp"].get("status_code", 0)
                        if status_code == 1002:  # rate limit exceeded
                            retry_count += 1
                            if retry_count <= max_retries:
                                print(f"    ⚠️  触发RPM限流 (尝试 {retry_count}/{max_retries})")
                                print(f"    ⏳ 等待 {self.RATE_LIMIT_WAIT} 秒后重试...")
                                time.sleep(self.RATE_LIMIT_WAIT)
                                continue
                            else:
                                raise RuntimeError(f"Rate limit exceeded after {max_retries} retries")

                    if "data" not in result or "audio" not in result["data"]:
                        raise RuntimeError(f"No audio data in response: {result}")

                    # MiniMax返回hex编码的音频数据
                    audio_hex = result["data"]["audio"]
                    audio_bytes = bytes.fromhex(audio_hex)
                    audio_chunks.append(audio_bytes)
                    success = True

                    # 成功后等待，避免触发限流（最后一个segment不用等）
                    if i < len(segments) - 1:
                        time.sleep(self.REQUEST_INTERVAL)

                except (requests.exceptions.SSLError, requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout) as e:
                    retry_count += 1
                    if retry_count <= max_retries:
                        wait_time = (2 ** retry_count) * 2  # 指数退避: 4s, 8s, 16s
                        print(f"    ⚠️  网络错误 (尝试 {retry_count}/{max_retries}): {type(e).__name__}")
                        print(f"    ⏳ 等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        raise RuntimeError(
                            f"Failed to generate segment {i+1}/{len(segments)} after {max_retries} retries: {str(e)}"
                        )

                except Exception as e:
                    # 其他错误不重试，直接抛出
                    raise RuntimeError(f"Failed to generate segment {i+1}/{len(segments)}: {str(e)}")

        # 合并所有音频片段
        print(f"Merging {len(audio_chunks)} audio segments...")
        self._merge_audio_chunks(audio_chunks, output_path)

        print(f"✓ Audio saved to: {output_path}")

        # Save to cache
        if self.cache:
            self.cache.set(text, self.model_name, {"model": self.model_name}, output_path)

        return output_path

    def _merge_audio_chunks(self, audio_chunks: List[bytes], output_path: Path):
        """
        合并多个MP3音频片段

        Args:
            audio_chunks: List of audio bytes
            output_path: Output file path
        """
        import subprocess
        import tempfile

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存每个chunk为临时文件
        temp_files = []
        for i, chunk in enumerate(audio_chunks):
            temp_file = Path(tempfile.gettempdir()) / f"tts_chunk_{i}_{int(time.time())}.mp3"
            with open(temp_file, 'wb') as f:
                f.write(chunk)
            temp_files.append(temp_file)

        try:
            # 使用ffmpeg合并
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                for temp_file in temp_files:
                    f.write(f"file '{temp_file.absolute()}'\n")
                concat_list = f.name

            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list,
                '-c', 'copy',
                '-y',
                str(output_path)
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            Path(concat_list).unlink()

        finally:
            # 清理临时文件
            for temp_file in temp_files:
                if temp_file.exists():
                    temp_file.unlink()


if __name__ == "__main__":
    # Example usage
    import argparse
    from config import Config

    parser = argparse.ArgumentParser(description="Generate audio using Gemini TTS v1.4")
    parser.add_argument("input_file", help="Input translations JSON file")
    parser.add_argument("-o", "--output", help="Output audio file")

    args = parser.parse_args()

    Config.validate()

    # Load translation
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        translated_text = data["translations"][0]["translated_text"]

    # Generate audio
    tts_generator = GeminiTTSGeneratorV14(api_key=Config.GEMINI_API_KEY)

    output_path = Path(args.output) if args.output else Path("output/test_v1.4.mp3")

    try:
        tts_generator.generate_audio(translated_text, output_path)
        print(f"\n✓ Audio generation complete!")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
