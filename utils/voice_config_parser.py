"""音色配置解析器 - 从 start_prompt.md 读取音色设置"""
import re
from pathlib import Path
from typing import Dict, Optional


class VoiceConfigParser:
    """
    从 start_prompt.md 解析音色配置

    配置格式示例:
    音色配置: speaker_0:{Grounded_Grace}, speaker_1:{Credible_Alex}
    """

    DEFAULT_VOICES = {
        "speaker_0": "Inspirational_girl",
        "speaker_1": "Deep_Voice_Man"
    }

    @staticmethod
    def parse_voice_config(prompt_file: Path = None) -> Dict[str, str]:
        """
        解析音色配置

        Args:
            prompt_file: start_prompt.md 文件路径（默认为项目根目录）

        Returns:
            音色映射字典，如 {"speaker_0": "Grounded_Grace", "speaker_1": "Credible_Alex"}
        """
        if prompt_file is None:
            prompt_file = Path(__file__).parent.parent / "start_prompt.md"

        if not prompt_file.exists():
            print(f"⚠️  未找到配置文件 {prompt_file}，使用默认音色")
            return VoiceConfigParser.DEFAULT_VOICES.copy()

        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配配置行：音色配置: speaker_0:{...}, speaker_1:{...}
        pattern = r'音色配置:\s*speaker_0:\{([^}]+)\}\s*,\s*speaker_1:\{([^}]+)\}'
        match = re.search(pattern, content)

        if match:
            speaker_0_voice = match.group(1).strip()
            speaker_1_voice = match.group(2).strip()

            voice_config = {
                "speaker_0": speaker_0_voice,
                "speaker_1": speaker_1_voice
            }

            print(f"✓ 从配置文件读取音色:")
            print(f"  speaker_0: {speaker_0_voice}")
            print(f"  speaker_1: {speaker_1_voice}")

            return voice_config
        else:
            print(f"⚠️  未在 {prompt_file.name} 中找到音色配置，使用默认音色")
            print(f"  提示：在文件中添加以下格式的配置行：")
            print(f"  音色配置: speaker_0:{{Grounded_Grace}}, speaker_1:{{Credible_Alex}}")
            return VoiceConfigParser.DEFAULT_VOICES.copy()

    @staticmethod
    def validate_voice_names(voice_config: Dict[str, str]) -> bool:
        """
        验证音色名称是否有效

        Args:
            voice_config: 音色配置字典

        Returns:
            是否所有音色都有效
        """
        # MiniMax 常用音色列表（可以扩展）
        valid_voices = {
            # 女声
            "Inspirational_girl", "Grounded_Grace", "Wise_Woman",
            "Cute_Girl", "Female_Narrator", "Gentle_Girl",

            # 男声
            "Deep_Voice_Man", "Credible_Alex", "Determined_Man",
            "Male_Narrator", "Mature_Man", "Young_Man",
        }

        all_valid = True
        for speaker, voice in voice_config.items():
            if voice not in valid_voices:
                print(f"⚠️  警告: 音色 '{voice}' 可能不在常用音色列表中")
                print(f"   如果API报错，请检查 MiniMax 官方文档确认音色名称")
                all_valid = False

        return all_valid


if __name__ == "__main__":
    # 测试解析
    config = VoiceConfigParser.parse_voice_config()
    print(f"\n解析结果: {config}")
    VoiceConfigParser.validate_voice_names(config)
