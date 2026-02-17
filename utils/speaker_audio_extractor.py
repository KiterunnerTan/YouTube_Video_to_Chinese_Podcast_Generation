"""Speaker音频提取器 - 从原视频提取各Speaker的参考音频用于语音克隆"""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AudioSegment:
    """音频片段信息"""
    speaker_id: str
    begin_time: int  # 毫秒
    end_time: int    # 毫秒
    text: str
    score: float = 0.0  # 评分

    @property
    def duration_ms(self) -> int:
        """片段时长（毫秒）"""
        return self.end_time - self.begin_time

    @property
    def duration_sec(self) -> float:
        """片段时长（秒）"""
        return self.duration_ms / 1000.0


class SpeakerAudioExtractor:
    """从视频中提取各Speaker的参考音频"""

    # 评分参数
    MIN_DURATION_SEC = 2.0      # 最小片段时长（秒）
    MAX_DURATION_SEC = 30.0     # 最大片段时长（秒）
    OPTIMAL_MIN_SEC = 5.0       # 最佳时长下限（秒）
    OPTIMAL_MAX_SEC = 15.0      # 最佳时长上限（秒）
    TARGET_TOTAL_SEC = 15.0     # 目标总时长（秒）
    MAX_TOTAL_SEC = 20.0        # 最大总时长（秒）
    SILENCE_DURATION_SEC = 0.3  # 片段间静音时长（秒）

    # 音频输出参数
    SAMPLE_RATE = 24000         # 采样率
    CHANNELS = 1                # 声道数（单声道）
    OUTPUT_FORMAT = "mp3"       # 输出格式

    def __init__(self, output_dir: Optional[Path] = None):
        """
        初始化Speaker音频提取器

        Args:
            output_dir: 输出目录（默认使用临时目录）
        """
        self.output_dir = output_dir or Path(tempfile.mkdtemp(prefix="speaker_audio_"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ SpeakerAudioExtractor 初始化完成")
        print(f"  输出目录: {self.output_dir}")

    def extract_speaker_audios(
        self,
        video_path: Path,
        asr_result: Dict[str, Any]
    ) -> Dict[str, Path]:
        """
        从视频中提取各Speaker的参考音频

        Args:
            video_path: 视频文件路径
            asr_result: ASR结果（含speaker_id, begin_time, end_time）

        Returns:
            Dict[speaker_id, audio_path]: 各Speaker的参考音频路径
        """
        if not video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        print(f"\n{'='*60}")
        print(f"开始提取Speaker参考音频")
        print(f"{'='*60}")
        print(f"视频文件: {video_path}")

        # 1. 解析ASR结果，提取所有片段
        segments = self._parse_asr_result(asr_result)
        print(f"✓ 解析到 {len(segments)} 个ASR片段")

        # 2. 按speaker_id分组
        speaker_segments = self._group_by_speaker(segments)
        print(f"✓ 检测到 {len(speaker_segments)} 个Speaker")

        # 3. 获取视频总时长（用于位置评分）
        video_duration_ms = self._get_video_duration_ms(video_path)
        print(f"✓ 视频总时长: {video_duration_ms/1000:.2f}秒")

        # 4. 为每个Speaker提取参考音频
        speaker_audios = {}
        for speaker_id, segs in speaker_segments.items():
            print(f"\n--- 处理 {speaker_id} ---")
            audio_path = self._extract_speaker_audio(
                video_path=video_path,
                speaker_id=speaker_id,
                segments=segs,
                video_duration_ms=video_duration_ms
            )
            if audio_path:
                speaker_audios[speaker_id] = audio_path
                print(f"✓ {speaker_id} 参考音频: {audio_path}")
            else:
                print(f"✗ {speaker_id} 无法提取有效参考音频")

        print(f"\n{'='*60}")
        print(f"提取完成: {len(speaker_audios)}/{len(speaker_segments)} 个Speaker")
        print(f"{'='*60}")

        return speaker_audios

    def _parse_asr_result(self, asr_result: Dict[str, Any]) -> List[AudioSegment]:
        """
        解析ASR结果，提取所有音频片段

        Args:
            asr_result: ASR结果

        Returns:
            音频片段列表
        """
        segments = []

        # 处理不同的ASR结果格式
        asr_segments = asr_result.get("segments", [])

        for segment in asr_segments:
            transcription = segment.get("transcription", {})

            # 支持 Recognition API ("sentence") 和 Transcription API ("sentences")
            sentences = transcription.get("sentence", []) or transcription.get("sentences", [])

            # 获取片段时间偏移
            segment_start_offset = segment.get("start_time_ms", 0)

            for sentence_data in sentences:
                text = sentence_data.get("text", "").strip()
                if not text:
                    continue

                # begin_time 和 end_time 是相对于片段开始的毫秒数
                begin_time = sentence_data.get("begin_time", 0)
                end_time = sentence_data.get("end_time", 0)

                # 转换为绝对时间戳
                absolute_begin = segment_start_offset + begin_time
                absolute_end = segment_start_offset + end_time

                # 获取speaker_id
                speaker_id = sentence_data.get("speaker_id")

                segments.append(AudioSegment(
                    speaker_id=speaker_id,
                    begin_time=absolute_begin,
                    end_time=absolute_end,
                    text=text
                ))

        return segments

    def _group_by_speaker(
        self,
        segments: List[AudioSegment]
    ) -> Dict[str, List[AudioSegment]]:
        """
        按speaker_id分组片段

        如果所有speaker_id都是None，视为单人（speaker_0）

        Args:
            segments: 音频片段列表

        Returns:
            按speaker_id分组的片段字典
        """
        # 检查是否所有speaker_id都是None
        all_null = all(seg.speaker_id is None for seg in segments)

        speaker_groups: Dict[str, List[AudioSegment]] = {}

        for seg in segments:
            if all_null:
                # 所有speaker_id都是None，视为单人
                speaker_id = "speaker_0"
            else:
                # 使用实际的speaker_id，None转为"unknown"
                speaker_id = f"speaker_{seg.speaker_id}" if seg.speaker_id is not None else "speaker_unknown"

            if speaker_id not in speaker_groups:
                speaker_groups[speaker_id] = []
            speaker_groups[speaker_id].append(seg)

        return speaker_groups

    def _score_segment(
        self,
        segment: AudioSegment,
        video_duration_ms: int
    ) -> float:
        """
        为片段评分

        评分因子：
        1. 时长适中（5-15秒最佳）
        2. 位于视频中段
        3. 语速稳定（通过文本长度/时长估算）

        Args:
            segment: 音频片段
            video_duration_ms: 视频总时长（毫秒）

        Returns:
            评分（0-100）
        """
        score = 0.0
        duration_sec = segment.duration_sec

        # 1. 时长评分（最高40分）
        if self.OPTIMAL_MIN_SEC <= duration_sec <= self.OPTIMAL_MAX_SEC:
            # 最佳时长范围，满分
            duration_score = 40.0
        elif duration_sec < self.OPTIMAL_MIN_SEC:
            # 时长偏短，按比例扣分
            duration_score = 40.0 * (duration_sec / self.OPTIMAL_MIN_SEC)
        else:
            # 时长偏长，按比例扣分
            ratio = (self.MAX_DURATION_SEC - duration_sec) / (self.MAX_DURATION_SEC - self.OPTIMAL_MAX_SEC)
            duration_score = 40.0 * max(0, ratio)
        score += duration_score

        # 2. 位置评分（最高30分）- 中段最佳
        if video_duration_ms > 0:
            # 计算片段中点在视频中的相对位置（0-1）
            mid_point = (segment.begin_time + segment.end_time) / 2
            relative_position = mid_point / video_duration_ms

            # 中段（0.2-0.8）最佳
            if 0.2 <= relative_position <= 0.8:
                position_score = 30.0
            elif relative_position < 0.2:
                # 开头部分，可能有噪音或开场白
                position_score = 30.0 * (relative_position / 0.2)
            else:
                # 结尾部分，可能有结束语
                position_score = 30.0 * ((1.0 - relative_position) / 0.2)
            score += position_score

        # 3. 语速稳定性评分（最高30分）
        # 通过文本长度/时长估算语速
        if duration_sec > 0:
            # 假设正常语速约为每秒3-5个字（中文）或每秒2-4个词（英文）
            chars_per_sec = len(segment.text) / duration_sec

            # 中文正常语速约3-5字/秒
            if 2.0 <= chars_per_sec <= 6.0:
                speed_score = 30.0
            elif chars_per_sec < 2.0:
                # 语速偏慢
                speed_score = 30.0 * (chars_per_sec / 2.0)
            else:
                # 语速偏快
                speed_score = 30.0 * max(0, (10.0 - chars_per_sec) / 4.0)
            score += speed_score

        return score

    def _select_best_segments(
        self,
        segments: List[AudioSegment],
        video_duration_ms: int
    ) -> List[AudioSegment]:
        """
        使用贪心算法选择最佳片段组合

        目标：累计15-20秒的参考音频

        Args:
            segments: 候选片段列表
            video_duration_ms: 视频总时长

        Returns:
            选中的片段列表
        """
        # 1. 筛选合格片段（排除时长<2秒或>30秒的片段）
        valid_segments = [
            seg for seg in segments
            if self.MIN_DURATION_SEC <= seg.duration_sec <= self.MAX_DURATION_SEC
        ]

        if not valid_segments:
            print(f"  警告: 没有符合时长要求的片段")
            # 放宽条件，只要时长>1秒的都可以
            valid_segments = [seg for seg in segments if seg.duration_sec > 1.0]
            if not valid_segments:
                return []

        # 2. 为每个片段评分
        for seg in valid_segments:
            seg.score = self._score_segment(seg, video_duration_ms)

        # 3. 按评分降序排序
        valid_segments.sort(key=lambda x: x.score, reverse=True)

        # 4. 贪心选择，累计15-20秒
        selected = []
        total_duration_sec = 0.0

        for seg in valid_segments:
            if total_duration_sec >= self.MAX_TOTAL_SEC:
                break

            # 如果加入这个片段后不会超过最大时长太多，就加入
            if total_duration_sec + seg.duration_sec <= self.MAX_TOTAL_SEC + 5.0:
                selected.append(seg)
                total_duration_sec += seg.duration_sec

                # 如果已经达到目标时长，可以停止
                if total_duration_sec >= self.TARGET_TOTAL_SEC:
                    break

        # 5. 按时间顺序排序（保持原始顺序）
        selected.sort(key=lambda x: x.begin_time)

        print(f"  选中 {len(selected)} 个片段，总时长: {total_duration_sec:.2f}秒")
        for i, seg in enumerate(selected):
            print(f"    [{i+1}] {seg.begin_time/1000:.2f}s-{seg.end_time/1000:.2f}s "
                  f"(时长:{seg.duration_sec:.2f}s, 评分:{seg.score:.1f})")

        return selected

    def _extract_speaker_audio(
        self,
        video_path: Path,
        speaker_id: str,
        segments: List[AudioSegment],
        video_duration_ms: int
    ) -> Optional[Path]:
        """
        为单个Speaker提取参考音频

        Args:
            video_path: 视频文件路径
            speaker_id: Speaker ID
            segments: 该Speaker的所有片段
            video_duration_ms: 视频总时长

        Returns:
            参考音频文件路径，或None
        """
        print(f"  共有 {len(segments)} 个片段")

        # 1. 选择最佳片段
        selected_segments = self._select_best_segments(segments, video_duration_ms)

        if not selected_segments:
            return None

        # 2. 提取并合并音频
        output_path = self.output_dir / f"{speaker_id}_reference.{self.OUTPUT_FORMAT}"

        try:
            self._extract_and_merge_segments(
                video_path=video_path,
                segments=selected_segments,
                output_path=output_path
            )
            return output_path
        except Exception as e:
            print(f"  ✗ 提取音频失败: {str(e)}")
            return None

    def _extract_and_merge_segments(
        self,
        video_path: Path,
        segments: List[AudioSegment],
        output_path: Path
    ):
        """
        使用FFmpeg提取并合并音频片段

        Args:
            video_path: 视频文件路径
            segments: 要提取的片段列表
            output_path: 输出文件路径
        """
        if len(segments) == 1:
            # 只有一个片段，直接提取
            seg = segments[0]
            self._extract_single_segment(
                video_path=video_path,
                start_ms=seg.begin_time,
                end_ms=seg.end_time,
                output_path=output_path
            )
        else:
            # 多个片段，需要分别提取后合并
            temp_files = []
            temp_dir = Path(tempfile.mkdtemp(prefix="speaker_segments_"))

            try:
                # 提取每个片段
                for i, seg in enumerate(segments):
                    temp_path = temp_dir / f"segment_{i}.{self.OUTPUT_FORMAT}"
                    self._extract_single_segment(
                        video_path=video_path,
                        start_ms=seg.begin_time,
                        end_ms=seg.end_time,
                        output_path=temp_path
                    )
                    temp_files.append(temp_path)

                # 生成静音文件
                silence_path = temp_dir / "silence.mp3"
                self._generate_silence(silence_path, self.SILENCE_DURATION_SEC)

                # 合并所有片段（片段间加静音）
                self._merge_with_silence(temp_files, silence_path, output_path)

            finally:
                # 清理临时文件
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _extract_single_segment(
        self,
        video_path: Path,
        start_ms: int,
        end_ms: int,
        output_path: Path
    ):
        """
        使用FFmpeg提取单个音频片段

        Args:
            video_path: 视频文件路径
            start_ms: 开始时间（毫秒）
            end_ms: 结束时间（毫秒）
            output_path: 输出文件路径
        """
        start_sec = start_ms / 1000.0
        duration_sec = (end_ms - start_ms) / 1000.0

        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_sec),
            '-t', str(duration_sec),
            '-vn',  # 不要视频
            '-ar', str(self.SAMPLE_RATE),
            '-ac', str(self.CHANNELS),
            '-y',  # 覆盖输出文件
            str(output_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

    def _generate_silence(self, output_path: Path, duration_sec: float):
        """
        生成静音音频文件

        Args:
            output_path: 输出文件路径
            duration_sec: 静音时长（秒）
        """
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'anullsrc=r={self.SAMPLE_RATE}:cl=mono',
            '-t', str(duration_sec),
            '-ar', str(self.SAMPLE_RATE),
            '-ac', str(self.CHANNELS),
            '-y',
            str(output_path)
        ]

        subprocess.run(cmd, capture_output=True, text=True, check=True)

    def _merge_with_silence(
        self,
        audio_files: List[Path],
        silence_path: Path,
        output_path: Path
    ):
        """
        合并音频文件，片段间加入静音

        Args:
            audio_files: 音频文件列表
            silence_path: 静音文件路径
            output_path: 输出文件路径
        """
        # 创建文件列表
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            filelist_path = f.name
            for i, audio_file in enumerate(audio_files):
                f.write(f"file '{audio_file.absolute()}'\n")
                # 在片段之间加入静音（最后一个片段后不加）
                if i < len(audio_files) - 1:
                    f.write(f"file '{silence_path.absolute()}'\n")

        try:
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-ar', str(self.SAMPLE_RATE),
                '-ac', str(self.CHANNELS),
                '-y',
                str(output_path)
            ]

            subprocess.run(cmd, capture_output=True, text=True, check=True)
        finally:
            Path(filelist_path).unlink()

    def _get_video_duration_ms(self, video_path: Path) -> int:
        """
        获取视频时长（毫秒）

        Args:
            video_path: 视频文件路径

        Returns:
            视频时长（毫秒）
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(video_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        duration_sec = float(info.get('format', {}).get('duration', 0))

        return int(duration_sec * 1000)

    def get_audio_info(self, audio_path: Path) -> Dict[str, Any]:
        """
        获取音频文件信息

        Args:
            audio_path: 音频文件路径

        Returns:
            音频信息字典
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            str(audio_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        format_info = info.get('format', {})

        duration = float(format_info.get('duration', 0))

        return {
            "duration_seconds": duration,
            "duration_ms": int(duration * 1000),
            "bit_rate": format_info.get('bit_rate', 'unknown'),
            "format_name": format_info.get('format_name', 'unknown'),
            "size_bytes": int(format_info.get('size', 0))
        }


if __name__ == "__main__":
    # 示例用法
    import argparse

    parser = argparse.ArgumentParser(description="从视频中提取Speaker参考音频")
    parser.add_argument("video_file", help="视频文件路径")
    parser.add_argument("asr_result", help="ASR结果JSON文件路径")
    parser.add_argument("-o", "--output-dir", help="输出目录")

    args = parser.parse_args()

    # 加载ASR结果
    with open(args.asr_result, 'r', encoding='utf-8') as f:
        asr_result = json.load(f)

    # 初始化提取器
    output_dir = Path(args.output_dir) if args.output_dir else None
    extractor = SpeakerAudioExtractor(output_dir=output_dir)

    try:
        # 提取Speaker音频
        speaker_audios = extractor.extract_speaker_audios(
            video_path=Path(args.video_file),
            asr_result=asr_result
        )

        # 显示结果
        print("\n=== 提取结果 ===")
        for speaker_id, audio_path in speaker_audios.items():
            info = extractor.get_audio_info(audio_path)
            print(f"{speaker_id}:")
            print(f"  文件: {audio_path}")
            print(f"  时长: {info['duration_seconds']:.2f}秒")
            print(f"  大小: {info['size_bytes']/1024:.1f}KB")

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        exit(1)
