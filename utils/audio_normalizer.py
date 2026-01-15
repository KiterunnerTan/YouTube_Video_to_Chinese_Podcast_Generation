"""音频音量标准化工具"""
import subprocess
from pathlib import Path
from typing import Optional


class AudioNormalizer:
    """音频音量标准化器 - 使用EBU R128标准"""

    def __init__(self, target_lufs: float = -16.0):
        """
        初始化音量标准化器

        Args:
            target_lufs: 目标响度（-16 LUFS 是播客行业标准）
        """
        self.target_lufs = target_lufs

    def normalize_audio(
        self,
        input_file: Path,
        output_file: Path,
        keep_original: bool = True
    ) -> bool:
        """
        标准化音频音量到目标响度

        Args:
            input_file: 输入音频文件
            output_file: 输出音频文件
            keep_original: 是否保留原始文件

        Returns:
            是否成功
        """
        if not input_file.exists():
            print(f"❌ 输入文件不存在: {input_file}")
            return False

        # 确保输出目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # ffmpeg loudnorm 命令
        cmd = [
            'ffmpeg',
            '-i', str(input_file),
            '-af', f'loudnorm=I={self.target_lufs}:TP=-1.5:LRA=11',
            '-c:a', 'libmp3lame',
            '-b:a', '128k',
            '-ar', '24000',
            '-ac', '1',
            '-y',
            str(output_file)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode == 0:
                # 验证输出文件
                if output_file.exists() and output_file.stat().st_size > 0:
                    return True
                else:
                    print(f"❌ 输出文件无效: {output_file}")
                    return False
            else:
                print(f"❌ ffmpeg执行失败:")
                print(f"stderr: {result.stderr[-500:]}")
                return False

        except subprocess.TimeoutExpired:
            print(f"❌ 音量标准化超时（5分钟）")
            return False
        except Exception as e:
            print(f"❌ 音量标准化异常: {str(e)}")
            return False

    def normalize_multiple(
        self,
        audio_files: list[Path],
        output_dir: Path,
        prefix: str = "normalized_"
    ) -> dict[str, Path]:
        """
        批量标准化多个音频文件

        Args:
            audio_files: 输入音频文件列表
            output_dir: 输出目录
            prefix: 输出文件前缀

        Returns:
            原始文件名 -> 标准化文件路径的映射
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        for idx, audio_file in enumerate(audio_files, 1):
            print(f"\n[{idx}/{len(audio_files)}] 标准化: {audio_file.name}")

            output_file = output_dir / f"{prefix}{audio_file.name}"

            success = self.normalize_audio(audio_file, output_file)

            if success:
                print(f"✓ 完成: {output_file.name}")
                results[audio_file.name] = output_file
            else:
                print(f"✗ 失败: {audio_file.name}")

        return results

    def get_audio_loudness(self, audio_file: Path) -> Optional[float]:
        """
        获取音频的当前响度值（LUFS）

        Args:
            audio_file: 音频文件

        Returns:
            响度值，或None（如果获取失败）
        """
        if not audio_file.exists():
            return None

        cmd = [
            'ffmpeg',
            '-i', str(audio_file),
            '-af', 'loudnorm=print_format=json',
            '-f', 'null',
            '-'
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            # 从stderr中提取JSON（ffmpeg输出到stderr）
            import json
            import re

            # 查找JSON块
            json_match = re.search(r'\{[^}]+\}', result.stderr)
            if json_match:
                loudness_data = json.loads(json_match.group(0))
                input_i = loudness_data.get('input_i')
                if input_i:
                    return float(input_i)

        except Exception as e:
            print(f"获取响度失败: {str(e)}")

        return None
