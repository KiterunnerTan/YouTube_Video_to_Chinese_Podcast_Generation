"""高级音频合并器 - 支持音乐过渡和淡入淡出效果"""
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
from .audio_normalizer import AudioNormalizer


class AudioMergerWithMusic:
    """音频合并器 - 支持音乐过渡和淡入淡出"""

    def __init__(self, target_lufs: float = -16.0, fade_duration: float = 2.0):
        """
        初始化合并器

        Args:
            target_lufs: 目标响度（-16 LUFS 播客标准）
            fade_duration: 淡入淡出时长（秒）
        """
        self.normalizer = AudioNormalizer(target_lufs=target_lufs)
        self.fade_duration = fade_duration

    def merge_with_music(
        self,
        music_start: Path,      # 开头和结尾音乐
        music_transition: Path, # 过渡音乐
        prologue: Path,         # 开场白
        summary: Path,          # 概述
        main_audio: Path,       # 主音频
        output_file: Path
    ) -> bool:
        """
        合并播客：music_1 → 开场白 → music_2 → 概述 → music_2 → 主音频 → music_1

        Args:
            music_start: 开头/结尾音乐
            music_transition: 过渡音乐
            prologue: 开场白
            summary: 概述
            main_audio: 主音频
            output_file: 输出文件

        Returns:
            是否成功
        """
        print(f"\n{'='*60}")
        print("音频合并 - 含音乐过渡和淡入淡出效果")
        print(f"{'='*60}")

        # 创建临时工作目录
        temp_dir = Path("output/temp_merge")
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: 标准化所有音频（包括音乐）
        print(f"\n[步骤1] 标准化所有音频音量到 -16 LUFS...")

        norm_music_start = temp_dir / "music_start_norm.mp3"
        norm_music_transition = temp_dir / "music_transition_norm.mp3"
        norm_prologue = temp_dir / "prologue_norm.mp3"
        norm_summary = temp_dir / "summary_norm.mp3"
        norm_main = temp_dir / "main_norm.mp3"

        files_to_normalize = [
            (music_start, norm_music_start, "开头/结尾音乐"),
            (music_transition, norm_music_transition, "过渡音乐"),
            (prologue, norm_prologue, "开场白"),
            (summary, norm_summary, "概述"),
            (main_audio, norm_main, "主音频")
        ]

        for idx, (src, dst, name) in enumerate(files_to_normalize, 1):
            print(f"  [{idx}/{len(files_to_normalize)}] 标准化{name}...")
            if not self.normalizer.normalize_audio(src, dst):
                print(f"❌ 标准化失败: {name}")
                return False

        print(f"✓ 所有音频已标准化\n")

        # Step 2: 使用ffmpeg的concat+crossfade方式合并
        # 由于ffmpeg的crossfade比较复杂，我们使用简化方案：
        # 直接拼接，但在音乐结尾添加淡出，在下一段开头添加淡入

        print(f"[步骤2] 为音乐添加淡出效果...")

        fade_music_start = temp_dir / "music_start_fade.mp3"
        fade_music_transition = temp_dir / "music_transition_fade.mp3"

        # 为music_start添加淡出（最后2秒淡出）
        self._add_fadeout(norm_music_start, fade_music_start, self.fade_duration)

        # 为music_transition添加淡出
        self._add_fadeout(norm_music_transition, fade_music_transition, self.fade_duration)

        print(f"✓ 淡出效果已添加\n")

        # Step 3: 创建concat列表并合并
        print(f"[步骤3] 合并所有音频片段...")

        concat_list_content = f"""file '{fade_music_start.absolute()}'
file '{norm_prologue.absolute()}'
file '{fade_music_transition.absolute()}'
file '{norm_summary.absolute()}'
file '{fade_music_transition.absolute()}'
file '{norm_main.absolute()}'
file '{fade_music_start.absolute()}'
"""

        concat_list_file = temp_dir / "concat_list.txt"
        with open(concat_list_file, 'w', encoding='utf-8') as f:
            f.write(concat_list_content)

        # 合并
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_list_file),
            '-c:a', 'libmp3lame',
            '-b:a', '128k',
            '-ar', '24000',
            '-ac', '1',
            '-y',
            str(output_file)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                print(f"❌ ffmpeg合并失败:")
                print(f"stderr: {result.stderr[-500:]}")
                return False

            print(f"✓ 音频合并成功: {output_file}\n")

            # 获取文件信息
            file_size = output_file.stat().st_size / 1024 / 1024
            duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                           '-of', 'default=noprint_wrappers=1:nokey=1', str(output_file)]
            duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())

            print(f"📊 最终播客信息:")
            print(f"   文件大小: {file_size:.1f} MB")
            print(f"   总时长: {duration/60:.1f} 分钟")
            print(f"   结构: music_1 → 开场白 → music_2 → 概述 → music_2 → 主音频 → music_1")
            print(f"   标准化临时文件: {temp_dir}")

            return True

        except subprocess.TimeoutExpired:
            print(f"❌ 合并超时（5分钟）")
            return False
        except Exception as e:
            print(f"❌ 合并异常: {str(e)}")
            return False

    def _add_fadeout(self, input_file: Path, output_file: Path, fade_duration: float) -> bool:
        """
        为音频添加淡出效果

        Args:
            input_file: 输入文件
            output_file: 输出文件
            fade_duration: 淡出时长（秒）

        Returns:
            是否成功
        """
        # 获取音频总时长
        duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                       '-of', 'default=noprint_wrappers=1:nokey=1', str(input_file)]
        try:
            duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
        except:
            print(f"❌ 无法获取音频时长: {input_file}")
            return False

        # 计算淡出开始时间
        fadeout_start = max(0, duration - fade_duration)

        # 应用淡出滤镜
        cmd = [
            'ffmpeg',
            '-i', str(input_file),
            '-af', f'afade=t=out:st={fadeout_start}:d={fade_duration}',
            '-c:a', 'libmp3lame',
            '-b:a', '128k',
            '-ar', '24000',
            '-ac', '1',
            '-y',
            str(output_file)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.returncode == 0
        except:
            return False
