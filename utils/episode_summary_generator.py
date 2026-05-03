"""节目概述生成器 - 使用Gemini REST API总结ASR文字稿"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
import re


def create_session_with_retries(max_retries=5, backoff_factor=1.0):
    """
    创建带有自动重试机制的requests session

    Args:
        max_retries: 最大重试次数
        backoff_factor: 重试间隔因子（指数退避）
    """
    session = requests.Session()

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "OPTIONS"],
        raise_on_status=False
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


class EpisodeSummaryGenerator:
    """生成播客节目概述"""

    def __init__(self, gemini_api_key: str, proxy: Optional[Dict[str, str]] = None):
        """
        初始化节目概述生成器

        Args:
            gemini_api_key: Gemini API Key
            proxy: 代理配置（可选，自动从环境变量读取）
        """
        self.api_key = gemini_api_key

        # 使用环境变量中的代理
        self.proxies = {
            'http': os.environ.get('HTTP_PROXY', ''),
            'https': os.environ.get('HTTPS_PROXY', '')
        } if os.environ.get('HTTP_PROXY') else None

        # 创建带有重试机制的session
        self.session = create_session_with_retries(max_retries=5, backoff_factor=1.0)

        # Gemini REST API endpoint
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def parse_start_prompt(self, start_prompt_file: Path) -> Dict[str, str]:
        """
        解析start_prompt.md文件，提取播客名、嘉宾信息和概述prompt

        Args:
            start_prompt_file: start_prompt.md文件路径

        Returns:
            包含podcast_name, guest_name, summary_prompt的字典
        """
        with open(start_prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取{}中的内容
        # 格式1: 播客名字是{播客名}，嘉宾是{嘉宾名}
        podcast_pattern = r'播客名字是\{([^}]+)\}'
        guest_pattern = r'嘉宾是\{([^}]+)\}'

        podcast_match = re.search(podcast_pattern, content)
        guest_match = re.search(guest_pattern, content)

        podcast_name = podcast_match.group(1) if podcast_match else "未知播客"
        guest_name = guest_match.group(1) if guest_match else "未知嘉宾"

        # 提取节目概述prompt（如果有）
        # 格式: 节目概述prompt: ...
        summary_prompt_pattern = r'节目概述prompt[:：]\s*(.+?)(?=\n\n|\Z)'
        summary_prompt_match = re.search(summary_prompt_pattern, content, re.DOTALL)
        summary_prompt = summary_prompt_match.group(1).strip() if summary_prompt_match else None

        print(f"✓ 播客名: {podcast_name}")
        print(f"✓ 嘉宾: {guest_name}")
        if summary_prompt:
            print(f"✓ 自定义概述prompt: {summary_prompt[:50]}...")

        return {
            "podcast_name": podcast_name,
            "guest_name": guest_name,
            "summary_prompt": summary_prompt
        }

    def load_asr_transcript(self, asr_file: Path) -> str:
        """
        加载ASR文字稿

        Args:
            asr_file: ASR结果JSON文件路径

        Returns:
            合并后的文字稿文本
        """
        with open(asr_file, 'r', encoding='utf-8') as f:
            asr_data = json.load(f)

        # 显示ASR文件metadata（如果有）
        metadata = asr_data.get('metadata', {})
        if metadata:
            print(f"\n📄 ASR文件信息:")
            print(f"  播客名: {metadata.get('podcast_name', '未知')}")
            print(f"  URL: {metadata.get('youtube_url', '未知')}")
            print(f"  创建时间: {metadata.get('created_at', '未知')}")
            print()

        # 合并所有segment的文本
        full_transcript = ""

        if 'segments' in asr_data:
            for segment in asr_data['segments']:
                # 跳过 transcription 为 None 的 segment（可能是过短的音频片段）
                if segment.get('transcription') is None:
                    continue
                # 格式1: transcription.sentence 结构（Qwen3 ASR）
                if 'transcription' in segment and isinstance(segment['transcription'], dict) and 'sentence' in segment['transcription']:
                    for sentence in segment['transcription']['sentence']:
                        full_transcript += sentence.get('text', '') + " "
                # 格式2: items 结构
                elif 'items' in segment:
                    for item in segment['items']:
                        full_transcript += item.get('text', '') + " "
                # 格式3: 直接 text 字段
                elif 'text' in segment:
                    full_transcript += segment.get('text', '') + "\n"
        elif isinstance(asr_data, list):
            for segment in asr_data:
                if 'items' in segment:
                    for item in segment['items']:
                        full_transcript += item.get('text', '') + " "
                else:
                    full_transcript += segment.get('text', '') + "\n"

        print(f"✓ ASR文字稿长度: {len(full_transcript)} 字符")

        return full_transcript.strip()

    def generate_summary(
        self,
        podcast_name: str,
        guest_name: str,
        transcript: str,
        target_length: int = 120,
        custom_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        使用Gemini REST API生成播客节目概述

        Args:
            podcast_name: 播客名称
            guest_name: 嘉宾名称
            transcript: ASR文字稿
            target_length: 目标字数（默认120字）
            custom_prompt: 自定义prompt（可选）

        Returns:
            生成的概述文本，或None
        """
        print(f"\n{'='*60}")
        print(f"生成节目概述")
        print(f"{'='*60}")
        print(f"播客: {podcast_name}")
        print(f"嘉宾: {guest_name}")
        print(f"目标字数: {target_length}字\n")

        # 使用自定义prompt或默认prompt
        if custom_prompt:
            prompt = f"""
{custom_prompt}

文字稿：
{transcript[:10000]}

请根据以上要求生成节目概述。

【重要提示】
- 必须完整生成约{target_length}字的概述，不要截断
- 必须使用情绪和节奏标记：停顿（……）、感叹（！）、疑问（？）
- 例如："想想看……AI竞争如此激烈！OpenAI如何应对？"
- 不要输出思考过程，直接输出最终完整版本
"""
        else:
            prompt = f"""
请根据以下播客文字稿，生成一段精彩的中文节目概述。

播客名称：{podcast_name}
嘉宾：{guest_name}

要求：
1. 字数：约{target_length + 30}字（可上下浮动15%）
2. 风格：简练精彩、引人入胜、适合播客朗读，带有情绪和节奏变化
3. 结构（⭐ v1.5新增嘉宾金句）：
   - 直接从本期核心内容开始（不要"欢迎收听"、"我是主持人"等开场语）
   - 概述2-3个核心讨论要点或亮点
   - ⭐ **必须包含一句嘉宾金句**：从文字稿中提取嘉宾最有力量、最有洞见的一句话，用引号标注
   - 结尾：用自然过渡语句引入正式内容，例如"让我们一起来听听..."
4. 语气：专业、热情、第一人称"我们"
5. 情绪和节奏增强（⭐重点）：
   - 使用停顿标记（……）在关键观点前、转折处，增加节奏感
   - 在重要内容用感叹号（！）增强情绪
   - 适当使用疑问句（？）引发思考
   - 有节奏变化：有慢有快
6. 避免：不要有标题、标签或元信息，直接输出可朗读的文本

**嘉宾金句要求**：
- 从文字稿中找出嘉宾说的最有力量、最有洞见、最能被引用的一句话
- 用引号标注，如：正如他所说……"AI会改变一切！"
- 金句应该简短有力（10-25字），能引发共鸣
- 金句示例：
  * "我们不是在做语音合成，我们是在让每个人都能成为创作者！"
  * "未来五年，90%的工作都会被重新定义。"
  * "你不会被AI淘汰，但你会被更会用AI的人淘汰！"

文字稿：
{transcript[:10000]}

请生成节目概述（重点：要有情绪和节奏变化，必须包含嘉宾金句）：
"""

        # 使用Gemini Pro模型
        url = f"{self.base_url}/gemini-2.5-pro:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{prompt}\n\n【重要】必须输出完整的约150字概述，不要截断，必须包含嘉宾金句，不要输出思考过程或草稿。直接输出最终版本。"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.9,
                "topP": 0.95,
                "maxOutputTokens": 4096,
                "candidateCount": 1
            }
        }

        # 增强的重试逻辑
        max_retries = 5
        retry_delays = [5, 10, 20, 30, 45]

        for attempt in range(max_retries):
            try:
                print(f"正在调用Gemini REST API生成概述... (尝试 {attempt + 1}/{max_retries})")

                response = self.session.post(
                    url,
                    json=payload,
                    proxies=self.proxies,
                    timeout=120
                )

                if response.status_code == 200:
                    result = response.json()

                    # 提取生成的文本
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]

                        # 检查是否有content字段
                        if 'content' not in candidate:
                            print(f"❌ 响应中缺少 'content' 字段")
                            print(f"candidate keys: {list(candidate.keys())}")
                            print(f"完整响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
                            return None

                        if 'parts' not in candidate['content']:
                            print(f"❌ 响应中缺少 'parts' 字段")
                            print(f"content keys: {list(candidate['content'].keys())}")
                            print(f"完整candidate: {json.dumps(candidate, indent=2, ensure_ascii=False)}")

                            # 检查是否因为安全过滤被阻止
                            if 'finishReason' in candidate:
                                print(f"⚠️  finishReason: {candidate['finishReason']}")

                            return None

                        # 遍历所有parts，找到text类型的内容（跳过thoughts）
                        summary = None
                        for part in candidate['content']['parts']:
                            if 'text' in part:
                                summary = part['text'].strip()
                                break

                        if summary:
                            print(f"\n✓ 概述生成成功")
                            print(f"✓ 字数: {len(summary)} 字")
                            print(f"\n{'-'*60}")
                            print(summary)
                            print(f"{'-'*60}\n")
                            return summary
                        else:
                            print(f"❌ 未找到text内容")
                            return None

                print(f"❌ 生成失败: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return None

            except (
                requests.exceptions.SSLError,
                requests.exceptions.ProxyError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout
            ) as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"⚠ 网络请求失败 (尝试 {attempt + 1}/{max_retries})，{delay}秒后重试...")
                    print(f"  错误类型: {type(e).__name__}")
                    # 重置session以清除可能损坏的连接
                    self.session = create_session_with_retries(max_retries=5, backoff_factor=1.0)
                    time.sleep(delay)
                    continue
                else:
                    print(f"❌ 生成失败: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    return None

            except Exception as e:
                print(f"❌ 生成失败: {str(e)}")
                import traceback
                traceback.print_exc()
                return None

        return None

    def generate_from_files(
        self,
        start_prompt_file: Path,
        asr_file: Path,
        target_length: int = 120
    ) -> Optional[str]:
        """
        从文件生成节目概述（一站式方法）

        Args:
            start_prompt_file: start_prompt.md文件路径
            asr_file: ASR结果文件路径
            target_length: 目标字数（默认120字）

        Returns:
            生成的概述文本，或None
        """
        # 解析播客信息
        podcast_info = self.parse_start_prompt(start_prompt_file)

        # 加载文字稿
        transcript = self.load_asr_transcript(asr_file)

        # 生成概述（使用自定义prompt如果有）
        summary = self.generate_summary(
            podcast_name=podcast_info['podcast_name'],
            guest_name=podcast_info['guest_name'],
            transcript=transcript,
            target_length=target_length,
            custom_prompt=podcast_info.get('summary_prompt')
        )

        return summary
