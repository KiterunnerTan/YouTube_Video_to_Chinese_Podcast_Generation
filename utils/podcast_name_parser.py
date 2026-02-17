"""播客节目名解析器

从 start_prompt.md 中解析节目名称，并清理为合法的文件名
"""
import re
from pathlib import Path
from typing import Optional


class PodcastNameParser:
    """播客节目名解析器"""

    @staticmethod
    def parse_podcast_name(start_prompt_file: Path = Path("start_prompt.md")) -> str:
        """从 start_prompt.md 解析节目名

        Args:
            start_prompt_file: start_prompt.md 文件路径

        Returns:
            节目名称（已清理为合法文件名）

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 无法解析节目名
        """
        if not start_prompt_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {start_prompt_file}")

        # 读取文件
        with open(start_prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取节目名: 播客名字是{节目名}
        pattern = r'播客名字是\{([^}]+)\}'
        match = re.search(pattern, content)

        if not match:
            raise ValueError("无法从配置文件中解析节目名，请确保格式为：播客名字是{节目名}")

        podcast_name = match.group(1).strip()

        # 清理为合法文件名
        cleaned_name = PodcastNameParser.sanitize_filename(podcast_name)

        return cleaned_name

    @staticmethod
    def parse_guest_name(start_prompt_file: Path = Path("start_prompt.md")) -> Optional[str]:
        """从 start_prompt.md 解析嘉宾名

        Args:
            start_prompt_file: start_prompt.md 文件路径

        Returns:
            嘉宾名称，如果未找到则返回 None
        """
        if not start_prompt_file.exists():
            return None

        with open(start_prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取嘉宾名: 嘉宾是{嘉宾名}
        pattern = r'嘉宾是\{([^}]+)\}'
        match = re.search(pattern, content)

        if not match:
            return None

        return match.group(1).strip()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名，移除非法字符

        Args:
            filename: 原始文件名

        Returns:
            清理后的合法文件名
        """
        # 移除或替换不合法的文件名字符
        # Windows 不允许: < > : " / \ | ? *
        # macOS/Linux 不允许: /

        # 替换常见的非法字符为下划线或中文符号
        replacements = {
            '/': '_',
            '\\': '_',
            ':': '：',  # 使用中文冒号
            '*': '',
            '?': '？',  # 使用中文问号
            '"': '"',   # 使用中文引号
            '<': '《',
            '>': '》',
            '|': '_',
        }

        cleaned = filename
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)

        # 移除首尾空格
        cleaned = cleaned.strip()

        # 如果文件名为空，使用默认名称
        if not cleaned:
            cleaned = "未命名播客"

        return cleaned


if __name__ == "__main__":
    # 测试
    try:
        podcast_name = PodcastNameParser.parse_podcast_name()
        print(f"解析到的节目名: {podcast_name}")
    except Exception as e:
        print(f"解析失败: {e}")
