"""播客节目文案生成器 - 使用Gemini生成专业播客介绍"""
import requests
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


class PodcastDescriptionGenerator:
    """生成专业的播客节目介绍文案"""

    def __init__(self, gemini_api_key: str, proxy: Optional[Dict[str, str]] = None):
        """
        初始化文案生成器

        Args:
            gemini_api_key: Gemini API Key
            proxy: 代理配置（可选）
        """
        self.api_key = gemini_api_key

        # 使用环境变量中的代理
        self.proxies = {
            'http': os.environ.get('HTTP_PROXY', ''),
            'https': os.environ.get('HTTPS_PROXY', '')
        } if os.environ.get('HTTP_PROXY') else None

        # Gemini REST API endpoint
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

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
                # 格式1: transcription.sentence 结构（Qwen3 ASR）
                if 'transcription' in segment and 'sentence' in segment['transcription']:
                    for sentence in segment['transcription']['sentence']:
                        full_transcript += sentence.get('text', '') + " "
                # 格式2: items 结构
                elif 'items' in segment:
                    for item in segment['items']:
                        full_transcript += item.get('text', '') + " "
                # 格式3: 直接 text 字段
                elif 'text' in segment:
                    full_transcript += segment.get('text', '') + "\n"

        print(f"✓ ASR文字稿长度: {len(full_transcript)} 字符")
        return full_transcript.strip()

    def generate_title(
        self,
        podcast_name: str,
        guest_name: str,
        transcript: str
    ) -> Optional[str]:
        """
        生成吸睛的播客节目标题

        Args:
            podcast_name: 播客名称
            guest_name: 嘉宾名称
            transcript: ASR文字稿

        Returns:
            生成的标题（20-30字），或None
        """
        print(f"\n{'='*80}")
        print(f"生成播客节目标题")
        print(f"{'='*80}")

        prompt = f"""
你是一位资深的播客运营专家，擅长撰写吸引眼球的播客标题。

请根据以下信息，为这期播客节目生成一个引人入胜的标题：

**原始播客名称**：{podcast_name}
**嘉宾**：{guest_name}

**文字稿**（前8000字符）：
{transcript[:8000]}

**要求**：

1. **字数限制**：必须严格控制在20-30个中文字（不包括标点）
2. **吸睛效果**：
   - 提炼最核心、最有冲击力的观点或信息
   - 使用具体的数字、事件、矛盾或悬念
   - 避免空泛描述，要有具体价值点
3. **标题类型**（选择最合适的一种）：
   - 数据型：突出关键数据或统计（例如：ChatGPT用户从4亿飙升到9亿）
   - 观点型：提炼嘉宾的核心观点或预言（例如：Sam Altman预言AGI 2027到来）
   - 对比型：展示矛盾或对比（例如：从API到企业级 OpenAI的增长秘密）
   - 悬念型：制造疑问或好奇（例如：OpenAI如何应对红色警报挑战）
4. **禁止**：
   - 不要使用过多标点符号（可用冒号、顿号）
   - 不要太泛泛，要具体
   - 不要夸大或误导
   - 不要少于20字或超过30字

**参考示例（必须达到这个长度标准）**：
- Sam Altman揭秘：ChatGPT用户暴涨到9亿 OpenAI如何制胜AI竞赛（29字）
- OpenAI应对红色警报：从竞争危机到API业务超越ChatGPT（27字）
- AI不会商品化 Sam Altman解读个性化和体验才是护城河（26字）

请只输出标题本身（20-30字），不要输出任何解释、标记或额外内容。
"""

        # 使用 Flash 模型生成标题（更快，token 消耗更少）
        url = f"{self.base_url}/gemini-2.0-flash-exp:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.9,
                "topP": 0.95,
                "maxOutputTokens": 150,
                "candidateCount": 1
            }
        }

        # 添加重试机制
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"⏳ 重试 {attempt}/{max_retries-1}...")
                    import time
                    time.sleep(retry_delay)

                print("正在调用Gemini API生成标题...")

                response = requests.post(
                    url,
                    json=payload,
                    proxies=self.proxies,
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()

                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            title = candidate['content']['parts'][0].get('text', '').strip()

                            # 移除可能的引号
                            title = title.strip('"').strip('"').strip("'")

                            print(f"\n✓ 标题生成成功")
                            print(f"✓ 字数: {len(title)} 字")
                            print(f"✓ 标题: {title}\n")

                            return title

                print(f"❌ 标题生成失败: {response.status_code}")
                print(f"Response: {response.text[:500]}")

                if attempt < max_retries - 1:
                    continue
                return None

            except Exception as e:
                print(f"❌ 标题生成失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    import traceback
                    traceback.print_exc()
                    return None

    def generate_description(
        self,
        podcast_name: str,
        guest_name: str,
        transcript: str,
        video_url: Optional[str] = None
    ) -> Optional[str]:
        """
        生成专业的播客节目介绍文案

        Args:
            podcast_name: 播客名称
            guest_name: 嘉宾名称
            transcript: ASR文字稿
            video_url: 原视频URL（可选）

        Returns:
            生成的文案，或None
        """
        # 先生成标题
        title = self.generate_title(podcast_name, guest_name, transcript)

        print(f"\n{'='*80}")
        print(f"生成播客节目介绍文案")
        print(f"{'='*80}")
        print(f"播客: {podcast_name}")
        print(f"嘉宾: {guest_name}\n")

        prompt = f"""
你是一位资深的播客运营专家，擅长撰写吸引人的播客节目介绍。

请根据以下信息，为播客节目生成一份专业的文案介绍：

**播客名称**：{podcast_name}
**嘉宾**：{guest_name}

**文字稿**（前10000字符）：
{transcript[:10000]}

**要求**：

1. **开篇段落**（严格1-2句话，不超过80字）：
   - 用吸引人的方式引出核心亮点
   - 点出嘉宾的独特价值或核心观点

2. **主体段落**（严格2段，每段恰好2句话，每段不超过100字）：
   - 简洁介绍嘉宾背景和本期核心内容
   - 突出最精彩的观点、案例或数据
   - 使用具体细节而非空泛描述

3. **时点内容 | Key Topics** 部分（严格4-5个话题点）：
   - 每个话题用简短标题（加粗）+ 恰好1句话说明（不超过35字）
   - 只涵盖最核心的亮点

4. **相关链接与资源** 部分：
   - 如果有视频URL，添加：[视频来源]{video_url if video_url else 'www.youtube.com'}

5. **结尾免责声明**（固定格式）：
   本播客采用虚拟主持人进行播客翻译的音频制作，因此有可能会有一些地方听起来比较奇怪。如想了解更多信息，请关注微信公众号"西经东译"获取AI最新资讯。

**关键限制（必须严格遵守）**：
- 开篇：≤80字
- 主体：2段，每段≤100字
- Key Topics：4-5个，每个说明≤35字
- **总长度必须严格控制在400-560字之间**

**风格要求**：
- 专业但不枯燥，有吸引力
- 用具体数据和案例，避免空泛
- 强调节目的独特价值
- 语言简洁流畅，去除所有冗余

**参考范例风格**（不要照搬内容）：
在大多数企业还在争论 AI 是否过度炒作时，Block（原 Square）已经通过内部自研的 AI Agent "Goose" 实现了惊人的效率提升。本期节目，我们邀请到了 Block 的首席技术官 Dhanji R. Prasanna，深度解析这家金融科技巨头如何转型为 AI 原生企业。

请直接输出完整文案，不要输出思考过程或标记。
"""

        # 使用Gemini Flash模型
        url = f"{self.base_url}/gemini-2.5-pro:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.8,
                "topP": 0.95,
                "maxOutputTokens": 4096,
                "candidateCount": 1
            }
        }

        # 添加重试机制
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"⏳ 重试 {attempt}/{max_retries-1}...")
                    import time
                    time.sleep(retry_delay)

                print("正在调用Gemini API生成文案...")

                response = requests.post(
                    url,
                    json=payload,
                    proxies=self.proxies,
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()

                    # 提取生成的文本
                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            description = candidate['content']['parts'][0].get('text', '').strip()

                            # 将标题添加到文案最前面
                            if title:
                                final_description = f"📻 {title}\n\n{'='*80}\n\n{description}"
                            else:
                                final_description = description

                            print(f"\n✓ 文案生成成功")
                            print(f"✓ 字数: {len(final_description)} 字")
                            print(f"\n{'-'*80}")
                            print(final_description)
                            print(f"{'-'*80}\n")

                            return final_description

                print(f"❌ 生成失败: {response.status_code}")
                print(f"Response: {response.text[:500]}")

                if attempt < max_retries - 1:
                    continue
                return None

            except Exception as e:
                print(f"❌ 生成失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    import traceback
                    traceback.print_exc()
                    return None

    def generate_from_files(
        self,
        start_prompt_file: Path,
        asr_file: Path,
        video_url: Optional[str] = None
    ) -> Optional[str]:
        """
        从文件生成播客介绍文案（一站式方法）

        Args:
            start_prompt_file: start_prompt.md文件路径
            asr_file: ASR结果文件路径
            video_url: 原视频URL（可选）

        Returns:
            生成的文案，或None
        """
        # 解析播客信息
        import re
        with open(start_prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取播客名和嘉宾
        podcast_pattern = r'播客名字是\{([^}]+)\}'
        guest_pattern = r'嘉宾是\{([^}]+)\}'

        podcast_match = re.search(podcast_pattern, content)
        guest_match = re.search(guest_pattern, content)

        podcast_name = podcast_match.group(1) if podcast_match else "未知播客"
        guest_name = guest_match.group(1) if guest_match else "未知嘉宾"

        print(f"✓ 播客名: {podcast_name}")
        print(f"✓ 嘉宾: {guest_name}")

        # 加载文字稿
        transcript = self.load_asr_transcript(asr_file)

        # 生成文案
        description = self.generate_description(
            podcast_name=podcast_name,
            guest_name=guest_name,
            transcript=transcript,
            video_url=video_url
        )

        return description
