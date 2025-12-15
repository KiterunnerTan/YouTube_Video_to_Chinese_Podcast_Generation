"""Gemini TTS audio generation module"""
import json
import time
import os
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests


class GeminiTTSGenerator:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash-preview-tts",
        voice_name: str = "Aoede"
    ):
        """
        Initialize Gemini TTS generator using REST API

        Args:
            api_key: Gemini API key
            model_name: Model to use for TTS (e.g., gemini-2.5-pro-preview-tts)
            voice_name: Voice to use for TTS
        """
        self.api_key = api_key
        self.model_name = model_name
        self.voice_name = voice_name
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

        # Setup proxy from environment variables
        self.proxies = {}
        if os.getenv('HTTP_PROXY'):
            self.proxies['http'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            self.proxies['https'] = os.getenv('HTTPS_PROXY')

        print(f"✓ Using Gemini TTS model: {model_name}")
        if self.proxies:
            print(f"✓ Using proxy: {self.proxies}")

    def generate_audio(
        self,
        text: str,
        output_path: Path,
        language: str = "zh-CN"
    ) -> Path:
        """
        Generate audio from text using Gemini TTS REST API

        Args:
            text: Text to convert to speech
            output_path: Path to save audio file
            language: Language code

        Returns:
            Path to generated audio file

        Raises:
            RuntimeError: If generation fails
        """
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
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": self.voice_name
                        }
                    }
                }
            }
        }

        params = {
            'key': self.api_key
        }

        # Retry logic for proxy connection issues
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                print(f"Generating audio for text (length: {len(text)})...")

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    params=params,
                    proxies=self.proxies if self.proxies else None,
                    timeout=120
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"TTS API request failed: {response.status_code} - {response.text}"
                    )

                result = response.json()

                # Extract audio data from response
                if 'candidates' not in result or len(result['candidates']) == 0:
                    raise RuntimeError(f"No candidates in TTS response: {result}")

                candidate = result['candidates'][0]
                if 'content' not in candidate:
                    raise RuntimeError(f"No content in candidate: {candidate}")

                parts = candidate['content'].get('parts', [])
                audio_data = None

                # Find audio part (inline_data with audio mime type)
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
                    raise RuntimeError(f"No audio data found in response: {parts}")

                # Decode base64
                audio_data = base64.b64decode(audio_base64)

                # Save audio - need to convert from PCM to MP3
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Check if it's PCM format
                if 'pcm' in mime_type.lower() or 'L16' in mime_type:
                    # Extract sample rate from mime type (e.g., "audio/L16;codec=pcm;rate=24000")
                    sample_rate = 24000  # default
                    if 'rate=' in mime_type:
                        try:
                            sample_rate = int(mime_type.split('rate=')[1].split(';')[0])
                        except:
                            pass

                    # Save as raw PCM first
                    import tempfile
                    import subprocess

                    with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as tmp_file:
                        tmp_file.write(audio_data)
                        pcm_path = tmp_file.name

                    # Convert PCM to MP3 using ffmpeg
                    cmd = [
                        'ffmpeg',
                        '-f', 's16le',  # 16-bit signed little-endian PCM
                        '-ar', str(sample_rate),  # Sample rate
                        '-ac', '1',  # Mono
                        '-i', pcm_path,
                        '-b:a', '128k',
                        '-y',
                        str(output_path)
                    ]

                    subprocess.run(cmd, capture_output=True, check=True)

                    # Clean up temp file
                    Path(pcm_path).unlink()
                else:
                    # Direct save if it's already MP3
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)

                print(f"✓ Audio saved to: {output_path}")
                return output_path

            except requests.exceptions.ProxyError as e:
                if attempt < max_retries - 1:
                    print(f"⚠ Proxy connection failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    raise RuntimeError(f"TTS API request failed after {max_retries} attempts: {str(e)}")

            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"TTS API request failed: {str(e)}")

            except Exception as e:
                raise RuntimeError(f"Failed to generate audio: {str(e)}")

    def generate_audio_for_segments(
        self,
        translations: List[Dict[str, Any]],
        output_dir: Path,
        delay_between_calls: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Generate audio for all translated segments

        Args:
            translations: List of translated segments
            output_dir: Directory to save audio files
            delay_between_calls: Delay between API calls

        Returns:
            List of segments with audio file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Generating audio for {len(translations)} segments...")

        audio_segments = []

        for i, segment in enumerate(translations):
            try:
                segment_id = segment.get("segment_id", i)
                translated_text = segment["translated_text"]

                # Generate audio file name
                audio_filename = f"segment_{segment_id:04d}.mp3"
                audio_path = output_dir / audio_filename

                # Generate audio
                self.generate_audio(
                    text=translated_text,
                    output_path=audio_path
                )

                audio_segment = {
                    "segment_id": segment_id,
                    "audio_file": str(audio_path),
                    "start_time_ms": segment.get("start_time_ms"),
                    "end_time_ms": segment.get("end_time_ms"),
                    "text": translated_text
                }

                audio_segments.append(audio_segment)

                # Rate limiting
                if i < len(translations) - 1:
                    time.sleep(delay_between_calls)

            except Exception as e:
                print(f"Error generating audio for segment {i}: {e}")
                raise  # Fail fast

        print(f"All {len(audio_segments)} audio segments generated successfully")
        return audio_segments

    def save_audio_manifest(self, audio_segments: List[Dict[str, Any]], output_path: Path):
        """Save audio generation manifest to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = {
            "total_segments": len(audio_segments),
            "audio_segments": audio_segments
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Audio manifest saved to: {output_path}")


if __name__ == "__main__":
    # Example usage
    import argparse
    from config import Config

    parser = argparse.ArgumentParser(description="Generate audio using Gemini TTS")
    parser.add_argument("input_file", help="Input translations JSON file")
    parser.add_argument("-o", "--output-dir", help="Output directory for audio files")
    parser.add_argument("-m", "--manifest", help="Output manifest JSON file")
    parser.add_argument(
        "-v", "--voice",
        default="Aoede",
        help="Voice name (default: Aoede)"
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="Delay between API calls in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    Config.validate()

    # Load translations
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        translations = data["translations"]

    # Generate audio
    tts_generator = GeminiTTSGenerator(
        api_key=Config.GEMINI_API_KEY,
        voice_name=args.voice
    )

    output_dir = Path(args.output_dir) if args.output_dir else Config.AUDIO_SEGMENTS_DIR

    try:
        audio_segments = tts_generator.generate_audio_for_segments(
            translations,
            output_dir=output_dir,
            delay_between_calls=args.delay
        )

        # Save manifest
        if args.manifest:
            tts_generator.save_audio_manifest(audio_segments, Path(args.manifest))
        else:
            print(json.dumps(audio_segments, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
