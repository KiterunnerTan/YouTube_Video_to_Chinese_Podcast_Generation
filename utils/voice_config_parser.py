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
        "speaker_0": "Chinese (Mandarin)_Crisp_Girl",
        "speaker_1": "Deep-voiced gentleman"
    }

    @staticmethod
    def parse_voice_config(prompt_file: Path = None) -> Optional[Dict[str, str]]:
        """
        解析音色配置（支持动态数量的speaker）

        Args:
            prompt_file: start_prompt.md 文件路径（默认为项目根目录）

        Returns:
            音色映射字典，如 {"speaker_0": "...", "speaker_1": "...", "speaker_2": "..."}
            如果用户未配置，返回 None（由调用方决定使用默认值或智能分配）
        """
        if prompt_file is None:
            prompt_file = Path(__file__).parent.parent / "start_prompt.md"

        if not prompt_file.exists():
            print(f"⚠️  未找到配置文件 {prompt_file}")
            return None

        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 动态匹配：找到音色配置行，然后解析所有 speaker_N:{voice} 模式
        # 支持格式：音色配置: speaker_0:{...}, speaker_1:{...}, speaker_2:{...}
        config_line_pattern = r'音色配置:\s*(.+?)(?:\n|$)'
        config_match = re.search(config_line_pattern, content)

        if not config_match:
            print(f"⚠️  未在 {prompt_file.name} 中找到音色配置")
            print(f"  提示：可在文件中添加以下格式手动指定音色：")
            print(f"  音色配置: speaker_0:{{Grounded_Grace}}, speaker_1:{{Credible_Alex}}")
            return None

        config_line = config_match.group(1)

        # 解析所有 speaker_N:{voice} 模式
        speaker_pattern = r'speaker_(\d+):\{([^}]+)\}'
        speaker_matches = re.findall(speaker_pattern, config_line)

        if not speaker_matches:
            print(f"⚠️  未在配置行中找到有效的speaker音色配置")
            return None

        voice_config = {}
        print(f"✓ 从配置文件读取音色:")
        for speaker_id, voice_name in speaker_matches:
            speaker_key = f"speaker_{speaker_id}"
            voice_config[speaker_key] = voice_name.strip()
            print(f"  {speaker_key}: {voice_name.strip()}")

        return voice_config

    @staticmethod
    def validate_voice_names(voice_config: Dict[str, str]) -> bool:
        """
        验证音色名称是否有效

        Args:
            voice_config: 音色配置字典

        Returns:
            是否所有音色都有效
        """
        # MiniMax 常用音色列表（中国区 + 国际区）
        valid_voices = {
            # 中国区女声
            "Chinese (Mandarin)_Crisp_Girl", "Chinese (Mandarin)_Gentle_Girl",

            # 中国区男声
            "Deep-voiced gentleman", "Chinese (Mandarin)_Male_Narrator",

            # 国际区女声（保留兼容）
            "Inspirational_girl", "Grounded_Grace", "Wise_Woman",
            "Cute_Girl", "Female_Narrator", "Gentle_Girl",

            # 国际区男声（保留兼容）
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
    if config:
        VoiceConfigParser.validate_voice_names(config)
    else:
        print("未找到用户配置，将使用智能音色分配")
