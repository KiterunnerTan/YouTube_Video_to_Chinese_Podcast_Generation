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
    """
    # 默认音色优先级队列（最多8个speaker）
    DEFAULT_VOICE_QUEUE = [
        ("speaker_0", "Kore"),      # 主持人（女）
        ("speaker_1", "Charon"),    # 主要嘉宾（男）
        ("speaker_2", "Puck"),      # 次要嘉宾（男，活泼）
        ("speaker_3", "Aoede"),     # 次要主持（女，表现力强）
        ("speaker_4", "Fenrir"),    # 专家A（男，力量感）
        ("speaker_5", "Leda"),      # 专家B（女，专业）
        ("speaker_6", "Orus"),      # 分析师（男，技术感）
        ("speaker_7", "Zephyr"),    # 旁白（中性）
    ]

    def __init__(self):
        """初始化音色管理器"""
        self.voice_mapping = dict(self.DEFAULT_VOICE_QUEUE)

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

        # 如果超出范围，循环复用（从speaker_2开始复用）
        # 避免覆盖主持人和主要嘉宾
        fallback_index = 2 + ((speaker_id - 2) % 6)
        fallback_speaker = f"speaker_{fallback_index}"
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
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-pro-preview-tts",
        voice_manager: Optional[VoiceManager] = None,
        enable_cache: bool = True
    ):
        """
        Initialize Gemini TTS generator v1.4 with multi-speaker support

        Args:
            api_key: Gemini API key
            model_name: TTS model name
            voice_manager: 音色管理器（可选，默认创建新的）
            enable_cache: Enable request caching to reduce API calls
        """
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.voice_manager = voice_manager or VoiceManager()
        self.cache = AudioCache() if enable_cache else None

        # Setup proxy
        self.proxies = {}
        if os.getenv('HTTP_PROXY'):
            self.proxies['http'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            self.proxies['https'] = os.getenv('HTTPS_PROXY')

        # Initialize proxy health checker
        self.proxy_checker = ProxyHealthChecker(self.proxies) if self.proxies else None

        print(f"✓ Using Gemini TTS model: {model_name}")
        if self.proxies:
            print(f"✓ Using proxy: {self.proxies}")
        if self.cache:
            print(f"✓ Request caching enabled")

    def generate_audio(
        self,
        text: str,
        output_path: Path,
        language: str = "zh-CN"
    ) -> Path:
        """
        Generate audio from text with multi-speaker support

        Args:
            text: Text with speaker markers (e.g., "speaker_0: hello\nspeaker_1: world")
            output_path: Path to save audio file
            language: Language code

        Returns:
            Path to generated audio file
        """
        # ⭐ CRITICAL: Check proxy health BEFORE making any API request
        # This prevents wasting API quota on failed proxy connections
        if self.proxy_checker:
            print("\n🔍 Checking proxy health before API request...")
            if not self.proxy_checker.is_healthy():
                raise RuntimeError(
                    "❌ Proxy health check failed. Please check your proxy settings.\n"
                    "This check prevents wasting API quota on doomed requests.\n"
                    f"Proxy: {self.proxies}"
                )
            print("✓ Proxy is healthy, proceeding with API request\n")

        # 构建multi-speaker配置 (要求text中只有speaker_0和speaker_1)
        speech_config = self.voice_manager.build_multi_speaker_config(text)

        # Check cache first
        if self.cache:
            cached_audio = self.cache.get(text, self.model_name, speech_config)
            if cached_audio:
                # Copy cached file to output path
                import shutil
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(cached_audio, output_path)
                print(f"✓ Using cached audio: {output_path}")
                return output_path

        # 打印使用的音色配置
        speakers = self.voice_manager.get_all_speakers_from_text(text)
        print(f"📻 Speakers detected: {len(speakers)}")
        for speaker_name in speakers:
            voice_name = "Kore" if speaker_name == "speaker_0" else "Charon"
            print(f"   {speaker_name}: {voice_name}")

        url = f"{self.base_url}/models/{self.model_name}:generateContent"

        headers = {
            'Content-Type': 'application/json',
        }

        payload = {
            "contents": [{
                "parts": [{
                    "text": text
                }]
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": speech_config
            }
        }

        params = {
            'key': self.api_key
        }

        # Retry logic with minimal retries
        # Since we check proxy health before making requests,
        # we only need 1 retry for transient network issues
        max_retries = 1  # Only 1 retry (total 2 attempts max)
        retry_delay = 10

        for attempt in range(max_retries):
            try:
                print(f"Generating audio (length: {len(text)} chars)...")

                # Use simple requests.post instead of Session with adapters
                # This avoids connection pool issues with proxy
                import warnings
                warnings.filterwarnings('ignore', message='Unverified HTTPS request')

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    params=params,
                    proxies=self.proxies if self.proxies else None,
                    verify=True,  # Use True to avoid proxy SSL issues
                    timeout=300
                )

                if response.status_code != 200:
                    # Check for quota errors - don't retry these
                    if response.status_code == 429:
                        error_msg = f"⚠️ API QUOTA EXCEEDED: {response.text}"
                        print(error_msg)
                        raise RuntimeError(error_msg)

                    raise RuntimeError(
                        f"TTS API request failed: {response.status_code} - {response.text}"
                    )

                result = response.json()

                # Extract audio data
                if 'candidates' not in result or len(result['candidates']) == 0:
                    raise RuntimeError(f"No candidates in TTS response: {result}")

                candidate = result['candidates'][0]
                if 'content' not in candidate:
                    raise RuntimeError(f"No content in candidate: {candidate}")

                parts = candidate['content'].get('parts', [])
                audio_base64 = None
                mime_type = None

                for part in parts:
                    if 'inlineData' in part:
                        inline_data = part['inlineData']
                        if inline_data.get('mimeType', '').startswith('audio/'):
                            mime_type = inline_data.get('mimeType')
                            audio_base64 = inline_data.get('data', '')
                            break

                if not audio_base64:
                    raise RuntimeError(f"No audio data found in response")

                # Decode base64
                audio_data = base64.b64decode(audio_base64)

                # Save audio
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Check if it's PCM format
                if 'pcm' in mime_type.lower() or 'L16' in mime_type:
                    # Extract sample rate
                    sample_rate = 24000
                    if 'rate=' in mime_type:
                        try:
                            sample_rate = int(mime_type.split('rate=')[1].split(';')[0])
                        except:
                            pass

                    # Convert PCM to MP3
                    import tempfile
                    import subprocess

                    with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as tmp_file:
                        tmp_file.write(audio_data)
                        pcm_path = tmp_file.name

                    cmd = [
                        'ffmpeg',
                        '-f', 's16le',
                        '-ar', str(sample_rate),
                        '-ac', '1',
                        '-i', pcm_path,
                        '-b:a', '128k',
                        '-y',
                        str(output_path)
                    ]

                    subprocess.run(cmd, capture_output=True, check=True)
                    Path(pcm_path).unlink()
                else:
                    # Direct save
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)

                print(f"✓ Audio saved to: {output_path}")

                # Save to cache for future use
                if self.cache:
                    self.cache.set(text, self.model_name, speech_config, output_path)

                return output_path

            except requests.exceptions.ProxyError as e:
                if attempt < max_retries - 1:
                    # Only 1 retry, fixed delay
                    print(f"⚠ Proxy connection failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    raise RuntimeError(f"TTS API request failed after {max_retries} attempts: {str(e)}")

            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"TTS API request failed: {str(e)}")

            except Exception as e:
                raise RuntimeError(f"Failed to generate audio: {str(e)}")


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
