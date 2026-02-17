"""Speaker 音色分析器 - 基于音频特征分析性别和音高

使用 librosa 提取基频（F0），判断：
- 性别：男声 85-180 Hz，女声 165-255 Hz
- 音高：高/低（用于在同性别音色池中匹配）
"""
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple, List
import json


class SpeakerVoiceAnalyzer:
    """分析 speaker 的声音特征，用于智能匹配预设音色"""

    # 性别判断阈值
    MALE_F0_RANGE = (85, 180)      # 男声基频范围
    FEMALE_F0_RANGE = (165, 255)   # 女声基频范围
    GENDER_THRESHOLD = 165         # 分界点：低于此为男声，高于此为女声

    # 音高判断阈值（在各自性别范围内的中位数）
    MALE_PITCH_THRESHOLD = 130     # 男声：<130 低音，>=130 高音
    FEMALE_PITCH_THRESHOLD = 210   # 女声：<210 低音，>=210 高音

    # 音色池（优化版：更有表现力，适合播客）
    VOICE_POOL = {
        "male": {
            "high": ["male-qn-jingying"],                    # 精英男声（年轻、活泼、有表现力）
            "low": ["Deep_Voice_Man"]                         # 深沉男声（有质感、适合播客）
        },
        "female": {
            "high": ["Inspirational_girl", "Chinese (Mandarin)_Crisp_Girl"],  # 有感染力、清脆
            "low": ["Chinese (Mandarin)_Gentle_Girl"]         # 温柔女声
        }
    }

    # 所有可用音色（用于去重时的备选）
    ALL_MALE_VOICES = ["male-qn-jingying", "Deep_Voice_Man"]
    ALL_FEMALE_VOICES = ["Inspirational_girl", "Chinese (Mandarin)_Crisp_Girl", "Chinese (Mandarin)_Gentle_Girl"]

    def __init__(self):
        """初始化分析器"""
        self._check_librosa()

    def _check_librosa(self):
        """检查 librosa 是否可用"""
        try:
            import librosa
            self.librosa = librosa
            self.librosa_available = True
        except ImportError:
            print("⚠️  librosa 未安装，将使用默认音色分配")
            print("   安装命令: pip install librosa")
            self.librosa_available = False

    def extract_audio_segment(
        self,
        video_path: Path,
        start_ms: int,
        end_ms: int,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        从视频中提取音频片段

        Args:
            video_path: 视频文件路径
            start_ms: 开始时间（毫秒）
            end_ms: 结束时间（毫秒）
            output_path: 输出路径（可选）

        Returns:
            音频文件路径
        """
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".wav"))

        start_sec = start_ms / 1000
        duration_sec = (end_ms - start_ms) / 1000

        # 限制提取时长，避免太长（10秒足够分析）
        duration_sec = min(duration_sec, 10.0)

        cmd = [
            'ffmpeg', '-y',
            '-i', str(video_path),
            '-ss', str(start_sec),
            '-t', str(duration_sec),
            '-vn',  # 不要视频
            '-ar', '22050',  # 采样率
            '-ac', '1',  # 单声道
            '-f', 'wav',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                return output_path
        except Exception as e:
            print(f"  ⚠️  提取音频失败: {e}")

        return None

    def analyze_pitch(self, audio_path: Path) -> Optional[float]:
        """
        分析音频的基频（F0）

        Args:
            audio_path: 音频文件路径

        Returns:
            平均基频（Hz），或 None
        """
        if not self.librosa_available:
            return None

        try:
            import numpy as np

            # 加载音频
            y, sr = self.librosa.load(str(audio_path), sr=22050)

            # 提取基频（使用 pyin 算法，更准确）
            f0, voiced_flag, voiced_probs = self.librosa.pyin(
                y,
                fmin=self.librosa.note_to_hz('C2'),  # ~65 Hz
                fmax=self.librosa.note_to_hz('C6'),  # ~1047 Hz
                sr=sr
            )

            # 过滤无效值，计算平均基频
            valid_f0 = f0[~np.isnan(f0)]
            if len(valid_f0) > 0:
                # 使用中位数，比平均值更稳定
                median_f0 = float(np.median(valid_f0))
                return median_f0

        except Exception as e:
            print(f"  ⚠️  基频分析失败: {e}")

        return None

    def detect_gender_and_pitch(self, f0: float) -> Tuple[str, str]:
        """
        根据基频判断性别和音高

        Args:
            f0: 基频（Hz）

        Returns:
            (gender, pitch): ("male"/"female", "high"/"low")
        """
        # 判断性别
        if f0 < self.GENDER_THRESHOLD:
            gender = "male"
            pitch = "high" if f0 >= self.MALE_PITCH_THRESHOLD else "low"
        else:
            gender = "female"
            pitch = "high" if f0 >= self.FEMALE_PITCH_THRESHOLD else "low"

        return gender, pitch

    def match_voice(self, gender: str, pitch: str, used_voices: List[str] = None) -> str:
        """
        根据性别和音高匹配音色

        Args:
            gender: "male" 或 "female"
            pitch: "high" 或 "low"
            used_voices: 已使用的音色列表（避免重复）

        Returns:
            匹配的音色ID
        """
        used_voices = used_voices or []

        # 获取推荐音色列表
        recommended = self.VOICE_POOL.get(gender, {}).get(pitch, [])

        # 先从推荐列表中找未使用的
        for voice in recommended:
            if voice not in used_voices:
                return voice

        # 如果推荐的都用了，从同性别的所有音色中找
        all_voices = self.ALL_MALE_VOICES if gender == "male" else self.ALL_FEMALE_VOICES
        for voice in all_voices:
            if voice not in used_voices:
                return voice

        # 实在找不到，返回第一个推荐的（允许重复）
        return recommended[0] if recommended else self.ALL_MALE_VOICES[0]

    def analyze_speakers_from_asr(
        self,
        video_path: Path,
        asr_result: Dict
    ) -> Dict[str, Dict]:
        """
        分析 ASR 结果中每个 speaker 的声音特征

        Args:
            video_path: 视频文件路径
            asr_result: ASR 结果（包含 segments）

        Returns:
            speaker 特征字典: {
                "speaker_0": {"gender": "male", "pitch": "low", "f0": 120.5},
                ...
            }
        """
        print("\n分析 speaker 声音特征...")

        if not self.librosa_available:
            print("  ⚠️  librosa 不可用，跳过分析")
            return {}

        # 收集每个 speaker 的发言时间段
        speaker_segments = {}
        segments = asr_result.get('segments', [])

        for segment in segments:
            transcription = segment.get('transcription', {})
            sentences = transcription.get('sentence', [])

            for sentence in sentences:
                speaker_id = sentence.get('speaker_id')
                if speaker_id is None:
                    speaker_id = 0  # 默认 speaker_0

                speaker_key = f"speaker_{speaker_id}"
                if speaker_key not in speaker_segments:
                    speaker_segments[speaker_key] = []

                speaker_segments[speaker_key].append({
                    'start': sentence.get('begin_time', 0),
                    'end': sentence.get('end_time', 0)
                })

        # 如果没有找到 speaker 分段，尝试从整个 segment 提取
        if not speaker_segments:
            print("  ⚠️  ASR 中没有 speaker 标记，使用整体分析")
            # 取前30秒作为样本
            speaker_segments["speaker_0"] = [{"start": 0, "end": 30000}]

        # 分析每个 speaker
        results = {}
        for speaker_key, time_segments in speaker_segments.items():
            print(f"  分析 {speaker_key}...")

            # 选取一个合适的片段（5-15秒，在中间位置）
            best_segment = self._select_best_segment(time_segments)
            if not best_segment:
                print(f"    ⚠️  没有找到合适的音频片段")
                continue

            # 提取音频
            audio_path = self.extract_audio_segment(
                video_path,
                best_segment['start'],
                best_segment['end']
            )

            if audio_path is None:
                print(f"    ⚠️  音频提取失败")
                continue

            try:
                # 分析基频
                f0 = self.analyze_pitch(audio_path)

                if f0 is not None:
                    gender, pitch = self.detect_gender_and_pitch(f0)
                    results[speaker_key] = {
                        "gender": gender,
                        "pitch": pitch,
                        "f0": round(f0, 1)
                    }
                    print(f"    ✓ F0={f0:.1f}Hz → {gender}/{pitch}")
                else:
                    print(f"    ⚠️  无法分析基频")

            finally:
                # 清理临时文件
                if audio_path.exists():
                    audio_path.unlink()

        return results

    def _select_best_segment(self, time_segments: List[Dict]) -> Optional[Dict]:
        """
        选择最适合分析的音频片段

        优先选择：
        1. 时长在 5-15 秒之间
        2. 位置在中间（避免开头结尾的噪音）
        """
        if not time_segments:
            return None

        # 按时长筛选
        valid_segments = []
        for seg in time_segments:
            duration = (seg['end'] - seg['start']) / 1000  # 秒
            if 3 <= duration <= 20:
                valid_segments.append(seg)

        if not valid_segments:
            # 没有合适时长的，取最长的
            valid_segments = sorted(time_segments, key=lambda x: x['end'] - x['start'], reverse=True)

        if not valid_segments:
            return None

        # 取中间位置的片段
        mid_index = len(valid_segments) // 2
        return valid_segments[mid_index]

    def auto_assign_voices(
        self,
        video_path: Path,
        asr_result: Dict,
        speaker_count: int
    ) -> Dict[str, str]:
        """
        自动为所有 speaker 分配音色

        Args:
            video_path: 视频文件路径
            asr_result: ASR 结果
            speaker_count: speaker 数量

        Returns:
            音色分配: {"speaker_0": "presenter_male", "speaker_1": "female-shaonv", ...}
        """
        print("\n" + "=" * 60)
        print("🎤 智能音色分配")
        print("=" * 60)

        # 分析 speaker 特征
        speaker_features = self.analyze_speakers_from_asr(video_path, asr_result)

        # 分配音色
        voice_mapping = {}
        used_voices = []

        for i in range(speaker_count):
            speaker_key = f"speaker_{i}"

            if speaker_key in speaker_features:
                # 有特征分析结果，智能匹配
                features = speaker_features[speaker_key]
                voice = self.match_voice(
                    features['gender'],
                    features['pitch'],
                    used_voices
                )
                print(f"  {speaker_key}: {features['gender']}/{features['pitch']} → {voice}")
            else:
                # 没有特征，使用默认规则
                # 交替分配男女声
                if i % 2 == 0:
                    voice = self.match_voice("male", "low", used_voices)
                else:
                    voice = self.match_voice("female", "low", used_voices)
                print(f"  {speaker_key}: (默认) → {voice}")

            voice_mapping[speaker_key] = voice
            used_voices.append(voice)

        print("=" * 60)
        return voice_mapping


# 便捷函数
def auto_assign_voices(
    video_path: Path,
    asr_result: Dict,
    speaker_count: int
) -> Dict[str, str]:
    """自动分配音色的便捷函数"""
    analyzer = SpeakerVoiceAnalyzer()
    return analyzer.auto_assign_voices(video_path, asr_result, speaker_count)


if __name__ == "__main__":
    # 测试用
    import sys

    if len(sys.argv) < 2:
        print("用法: python speaker_voice_analyzer.py <video_path> [asr_json_path]")
        sys.exit(1)

    video_path = Path(sys.argv[1])
    if not video_path.exists():
        print(f"视频文件不存在: {video_path}")
        sys.exit(1)

    # 加载 ASR 结果
    if len(sys.argv) >= 3:
        asr_path = Path(sys.argv[2])
        with open(asr_path, 'r', encoding='utf-8') as f:
            asr_result = json.load(f)
    else:
        asr_result = {"segments": []}

    # 分析
    analyzer = SpeakerVoiceAnalyzer()
    features = analyzer.analyze_speakers_from_asr(video_path, asr_result)

    print("\n分析结果:")
    print(json.dumps(features, indent=2, ensure_ascii=False))
