"""Gemini translation module v1.4 - Natural TTS with no emotion markers"""
import json
import time
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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


def count_speakers(asr_result: Dict[str, Any]) -> int:
    """
    从ASR结果识别speaker数量

    Args:
        asr_result: ASR结果字典，包含segments列表

    Returns:
        speaker数量：
        - 如果所有segment的speaker_id都是null，返回1
        - 否则返回不同speaker_id的数量
    """
    segments = asr_result.get("segments", [])

    if not segments:
        return 1

    speaker_ids = set()
    all_null = True

    for segment in segments:
        speaker_id = segment.get("speaker_id")
        if speaker_id is not None:
            all_null = False
            speaker_ids.add(speaker_id)

    if all_null:
        return 1

    return len(speaker_ids) if speaker_ids else 1


class GeminiTranslatorV14:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro"):
        """
        Initialize Gemini translator using REST API

        Args:
            api_key: Gemini API key
            model_name: Model to use for translation
        """
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

        # Setup proxy from environment variables
        self.proxies = {}
        if os.getenv('HTTP_PROXY'):
            self.proxies['http'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            self.proxies['https'] = os.getenv('HTTPS_PROXY')

        # 创建带有重试机制的session
        self.session = create_session_with_retries(max_retries=5, backoff_factor=1.0)

        print(f"✓ Using Gemini model: {model_name}")
        if self.proxies:
            print(f"✓ Using proxy: {self.proxies}")

    def _call_gemini_api(self, prompt: str) -> str:
        """
        Call Gemini API using REST endpoint with enhanced retry logic
        """
        url = f"{self.base_url}/models/{self.model_name}:generateContent"

        headers = {
            'Content-Type': 'application/json',
        }

        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }

        params = {
            'key': self.api_key
        }

        # Enhanced retry logic for SSL/network issues
        max_retries = 5
        retry_delays = [5, 10, 20, 30, 45]  # 递增延迟

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    url,
                    headers=headers,
                    json=payload,
                    params=params,
                    proxies=self.proxies if self.proxies else None,
                    timeout=180  # 增加超时时间
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"API request failed: {response.status_code} - {response.text}"
                    )

                result = response.json()

                # Extract text from response
                if 'candidates' not in result or len(result['candidates']) == 0:
                    raise RuntimeError(f"No candidates in response: {result}")

                candidate = result['candidates'][0]
                if 'content' not in candidate:
                    raise RuntimeError(f"No content in candidate: {candidate}")

                parts = candidate['content'].get('parts', [])
                if len(parts) == 0:
                    raise RuntimeError(f"No parts in content: {candidate['content']}")

                text = parts[0].get('text', '')
                return text

            except (
                requests.exceptions.SSLError,        # SSL错误（如SSL握手失败）
                requests.exceptions.ProxyError,      # 代理连接错误
                requests.exceptions.ConnectionError, # 网络连接错误
                requests.exceptions.Timeout          # 请求超时
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
                    raise RuntimeError(f"API请求失败，已重试{max_retries}次: {str(e)}")

            except requests.exceptions.RequestException as e:
                # 其他HTTP错误（如400, 500等）直接抛出，不重试
                raise RuntimeError(f"API request failed: {str(e)}")

    def _create_translation_prompt_v14(
        self,
        segments: List[Dict[str, Any]],
        target_segment_index: int,
        speaker_count: int = 2
    ) -> str:
        """
        Create translation prompt for v1.4 (no emotion markers)

        Args:
            segments: List of ASR segments
            target_segment_index: Index of the segment to translate
            speaker_count: Number of speakers (1=monologue, 2+=dialogue)
        """
        # Get context window
        context_segments = []
        start_idx = max(0, target_segment_index - 1)
        end_idx = min(len(segments), target_segment_index + 2)

        for i in range(start_idx, end_idx):
            context_segments.append(segments[i])

        # Build prompt based on speaker count
        if speaker_count == 1:
            prompt = self._create_monologue_prompt()
        else:
            prompt = self._create_dialogue_prompt(speaker_count)

        # Add context segments
        for i, seg in enumerate(context_segments):
            segment_idx = start_idx + i
            formatted_text = seg.get("formatted_text", "")

            if segment_idx == target_segment_index:
                prompt += f"\n【需要翻译 - Segment {segment_idx}】:\n{formatted_text}\n"
            else:
                prompt += f"\n【上下文 - Segment {segment_idx}】:\n{formatted_text}\n"

        # Add output requirements based on speaker count
        if speaker_count == 1:
            prompt += self._create_monologue_output_requirements()
        else:
            prompt += self._create_dialogue_output_requirements()

        return prompt

    def _create_monologue_prompt(self) -> str:
        """Create prompt for single speaker (monologue) content"""
        return """你是一个专业的播客翻译专家。请将以下英文独白翻译成自然流畅、有节奏感的中文播客内容。

【单人独白翻译策略】

**核心原则**：忠实还原 + 自然节奏 + 保持内容深度

这是一个单人独白内容，将使用MiniMax Speech 2.6 HD引擎播放。你的任务是：
1. **完整翻译所有内容**，不遗漏任何部分
2. **保持自然的播客节奏**，让听众听起来舒服
3. **保持内容的含金量和深度**，不过度口语化

【⭐ TTS情感优化（核心！）- 避免低沉缓慢的朗读】

TTS引擎会根据文本语义自动推断情感。某些表达方式会触发"低沉缓慢"模式，必须通过**调整句子结构和节奏**来避免，但**不能牺牲内容深度**。

**策略一：金句保护（不改内容，改结构）**
金句/核心观点本身不动，通过前后衔接避免孤立：
- ❌ "能力越大，风险也就越大。"（孤立，TTS会读得很重）
- ✅ "当然，能力越大，风险也就越大，这是一体两面的。"
- ❌ "AI会改变一切。"（孤立）
- ✅ "说实话，AI会改变一切，这一点已经越来越明显了。"

**策略二：负面词"减重"（不口语化，用更中性的表达）**
- "做出了不明智的决定" → "做出了不太明智的选择"（加"不太"减轻程度）
- "有点吓人" → "有点让人意外"（中性化，保持书面）
- "太痛苦了" → "挺折腾的"（轻量化但不失深度）
- "毫无意义" → "意义不大"（减轻否定程度）
- "很可怕" → "挺有挑战的"（中性化）

**策略三：技术叙述"提速"（省略号→逗号，序列后加评价）**
- ❌ "它读取了推文内容……理解了这是一个bug……它检查了Git仓库"（省略号拖慢节奏）
- ✅ "它读取了推文内容，理解了这是一个bug，然后检查了Git仓库——整个过程完全自动。"
关键：把省略号换成逗号，在动作序列**结束后**加评价，而不是中间插入。

**策略四：悬念揭晓"提速"（省略号→语气词）**
- ❌ "但结果……什么都没发生"（省略号让TTS酝酿低沉）
- ✅ "但结果呢，什么都没发生"（"呢"让语气轻快）
- ❌ "结果嘛……要么是崩溃"
- ✅ "结果嘛，要么是崩溃，要么是获得新能力"

**策略五：反思句"脱孤"（让反思句不孤立）**
- ❌ "我当时其实没想自己动手做这个。"（孤立的反思句，TTS会沉重）
- ✅ "说实话，我当时其实没想自己动手做这个，因为我以为大公司会做。"
关键：前加引入词，后接原因/行动，不让反思句独立。

**省略号使用规则（收紧）**：
- ✅ 只用于：强调前的蓄力（"这意味着……整整90%！"）、积极情感的节奏感
- ❌ 禁止用于：平淡叙述中拖节奏、悬念铺垫、反思性内容

【⚠️ 重要：不要遗漏任何内容】

1. **开场白必须保留**：
   - "Welcome everyone"、"Hello everyone"、"My guest today is..." → 完整翻译
   - 主持人介绍嘉宾的内容 → 完整翻译
   - ✅ 示例："大家好，欢迎收听。今天我的嘉宾是Peter，他是Claude的创造者..."

2. **嘉宾介绍必须保留**：
   - 嘉宾的背景、身份、成就介绍 → 完整翻译
   - 不要因为是"套话"就省略

3. **结尾语必须保留**：
   - "Thanks for listening"、"See you next time" → 完整翻译
   - 结束语、致谢、预告 → 完整翻译

【⭐ 节奏和停顿（重要！）】

**停顿标记 `……` 的正确使用**：
- ✅ 强调前蓄力："这意味着……整整90%！"
- ✅ 积极情感节奏："我发现……这真的太棒了！"
- ❌ 平淡叙述中拖节奏："它读取了……理解了……检查了……"（用逗号代替）
- ❌ 悬念铺垫变低沉："但结果……"（用"但结果呢，"代替）
- ❌ 反思内容中："我当时……其实没想……"（直接连贯表达）

**数字强调**（必须增强）：
- ✅ "整整90%！"、"不到15%！"、"从90%直接降到10%！"
- ❌ "90%"（太平淡）

【⭐ 内容深度保护原则】

**核心思想**：保持播客的含金量，不过度口语化

1. **金句/核心观点**（保持权威，通过结构避免TTS低沉）：
   - ✅ "说实话，AI会改变一切，这一点已经越来越明显了。"（前后衔接）
   - ❌ "你知道，我觉得吧，AI真的会改变一切"（过度口语化）

2. **话题过渡处**（适度使用引入词）：
   - 话题切换："说到这个,"、"接下来,"
   - 举例引入："比如说,"、"举个例子,"
   - ⚠️ 不要每句话都加，只在话题转换时用

3. **技术描述**（保持专业感，但节奏流畅）：
   - ✅ "它读取了推文，理解了问题，然后直接修复——整个过程完全自动。"
   - ❌ "它读取了推文……理解了问题……然后修复……"（太拖沓）

【输出格式】

⚠️ **重要：只使用speaker_0**

```
speaker_0: 大家好，欢迎收听。今天我想和大家聊聊……AI的未来。
speaker_0: 在过去的一年里，我们见证了……整整90%的技术突破都发生在这个领域！这个数字太惊人了。
speaker_0: 说到这个，这意味着什么呢？意味着……未来五年，90%的工作都会被重新定义。
speaker_0: 比如说，我们来看看教育领域。传统的教学方式……正在被AI彻底颠覆。
```

**Speaker分配规则:**
- speaker_0: 独白讲述者
- ⚠️ 禁止使用speaker_1, speaker_2等

以下是内容（包含上下文，但你只需要翻译标记为【需要翻译】的部分）：

"""

    def _create_dialogue_prompt(self, speaker_count: int) -> str:
        """Create prompt for multi-speaker (dialogue) content"""
        # Speaker mapping note for 3+ speakers
        speaker_mapping_note = ""
        if speaker_count >= 3:
            speaker_mapping_note = """
【多人对话Speaker映射】

原始内容有3人或以上，但输出只使用speaker_0、speaker_1、speaker_2：
- speaker_0: 主持人（提问、引导）
- speaker_1: 主嘉宾（主要观点输出者）
- speaker_2: 其他嘉宾（补充观点、不同视角）

"""

        return f"""你是一个专业的播客翻译专家和对话脚本作家。请将以下英文对话翻译成极具真实感的中文播客对话。

【双人/多人对话翻译策略】

**核心原则**：完整翻译 + 保护金句完整性 + 保持内容深度

这次翻译将使用MiniMax Speech 2.6 HD引擎，它具备强大的语义理解能力，能根据文本内容自动推断并表达情绪。
你的任务是：**完整翻译所有内容，保持金句的权威感和内容深度，同时避免TTS进入低沉模式**。
{speaker_mapping_note}
【⭐ TTS情感优化（核心！）- 避免低沉缓慢的朗读】

TTS引擎会根据文本语义自动推断情感。某些表达方式会触发"低沉缓慢"模式，必须通过**调整句子结构和节奏**来避免，但**不能牺牲内容深度**。

**策略一：金句保护（不改内容，改结构）**
金句/核心观点本身不动，通过前后衔接避免孤立：
- ❌ "能力越大，风险也就越大。"（孤立，TTS会读得很重）
- ✅ "当然，能力越大，风险也就越大，这是一体两面的。"
- ❌ "AI会改变一切。"（孤立）
- ✅ "说实话，AI会改变一切，这一点已经越来越明显了。"

**策略二：负面词"减重"（不口语化，用更中性的表达）**
- "做出了不明智的决定" → "做出了不太明智的选择"（加"不太"减轻程度）
- "有点吓人" → "有点让人意外"（中性化，保持书面）
- "太痛苦了" → "挺折腾的"（轻量化但不失深度）
- "毫无意义" → "意义不大"（减轻否定程度）
- "很可怕" → "挺有挑战的"（中性化）

**策略三：技术叙述"提速"（省略号→逗号，序列后加评价）**
- ❌ "它读取了推文内容……理解了这是一个bug……它检查了Git仓库"（省略号拖慢节奏）
- ✅ "它读取了推文内容，理解了这是一个bug，然后检查了Git仓库——整个过程完全自动。"
关键：把省略号换成逗号，在动作序列**结束后**加评价，而不是中间插入。

**策略四：悬念揭晓"提速"（省略号→语气词）**
- ❌ "但结果……什么都没发生"（省略号让TTS酝酿低沉）
- ✅ "但结果呢，什么都没发生"（"呢"让语气轻快）
- ❌ "结果嘛……要么是崩溃"
- ✅ "结果嘛，要么是崩溃，要么是获得新能力"

**策略五：反思句"脱孤"（让反思句不孤立）**
- ❌ "我当时其实没想自己动手做这个。"（孤立的反思句，TTS会沉重）
- ✅ "说实话，我当时其实没想自己动手做这个，因为我以为大公司会做。"
关键：前加引入词，后接原因/行动，不让反思句独立。

**省略号使用规则（收紧）**：
- ✅ 只用于：强调前的蓄力（"这意味着……整整90%！"）、积极情感的节奏感
- ❌ 禁止用于：平淡叙述中拖节奏、悬念铺垫、反思性内容

【⚠️ 重要：不要遗漏任何内容】

1. **开场白必须保留**：
   - "Welcome everyone"、"Hello everyone"、"My guest today is..." → 完整翻译
   - 主持人介绍嘉宾的内容 → 完整翻译
   - ✅ 示例："大家好，欢迎收听。今天我的嘉宾是Peter，他是Claude的创造者..."

2. **嘉宾介绍必须保留**：
   - 嘉宾的背景、身份、成就介绍 → 完整翻译
   - 不要因为是"套话"就省略

3. **结尾语必须保留**：
   - "Thanks for listening"、"See you next time" → 完整翻译
   - 结束语、致谢、预告 → 完整翻译

【⭐ 金句和强逻辑段落保护】

**核心思想**：金句和数据论述是内容的精华，必须保持完整性和深度

1. **保护金句完整性，不插入回应**：
   - 嘉宾的核心洞见、经典语录 → 让嘉宾说完整，不被打断
   - 数据结论、重要判断 → 保持原文力度，不稀释
   - ✅ 示例："说实话，AI会改变一切，这一点已经越来越明显了。"
   - ❌ 避免：在金句中间插入"哦真的吗？"

2. **让嘉宾说完完整观点再切换speaker**：
   - 一个话题/论点由一个人完整表达（3-5句）
   - 不要每句话都让主持人插嘴

【⭐ 简单回应处理规则】

**省略不生成TTS的回应**（这些词不产生实际价值）：
- 中文：嗯、是的、对、好的、OK、明白、了解、哦
- 英文：Yeah、Right、Okay、Uh-huh、I see、Got it、Sure

**保留的回应**（满足任一条件）：
- 带情绪的回应："真的假的？"、"不会吧！"、"哇，太厉害了！"
- 引导性追问："那你们是怎么解决的？"、"具体是什么意思？"
- 超过5个字的实质内容

【⭐ 节奏和停顿（重要！）】

**停顿标记 `……` 的正确使用**：
- ✅ 强调前蓄力："这意味着……整整90%！"
- ✅ 积极情感节奏："我发现……这真的太棒了！"
- ❌ 平淡叙述中拖节奏："它读取了……理解了……检查了……"（用逗号代替）
- ❌ 悬念铺垫变低沉："但结果……"（用"但结果呢，"代替）
- ❌ 反思内容中："我当时……其实没想……"（直接连贯表达）

**数字强调**：✅ "整整90%！"、"不到15%！"

【内容深度保护原则】

1. **金句/核心观点**（保持权威，通过结构避免TTS低沉）：
   - ✅ "说实话，AI会改变一切，这一点已经越来越明显了。"
   - ❌ "你知道，我觉得吧，AI真的会改变一切"（过度口语化）

2. **对话互动**（保持自然）：
   - 主持人提问、追问 → 自然口语化
   - 过渡、衔接 → 适度使用引入词

【输出格式】

⚠️ **重要限制: 只使用speaker_0和speaker_1{"和speaker_2" if speaker_count >= 3 else ""}**

```
speaker_0: 大家好，欢迎收听本期节目。今天我们的嘉宾是Peter，一个非常有趣的AI工具的创造者。Peter，欢迎你！
speaker_1: 谢谢，很高兴来到这里。
speaker_0: 那你们是怎么解决这个问题的？
speaker_1: 我们用了一个非常简单但有效的方法。首先，让AI来审查代码。然后，用不同的模型交叉验证。最后，人工做最终确认。这个流程让我们的效率提升了整整300%。
speaker_0: 哇，300%！这个提升太惊人了。
```

**Speaker分配规则:**
- speaker_0: 主持人/提问者 (女声)
- speaker_1: {"主嘉宾/回答者 (男声)" if speaker_count >= 3 else "嘉宾/回答者 (男声)"}
{"- speaker_2: 其他嘉宾 (补充观点)" if speaker_count >= 3 else ""}
- ⚠️ 禁止使用speaker_{"3" if speaker_count >= 3 else "2"}, speaker_{"4" if speaker_count >= 3 else "3"}等

以下是对话内容（包含上下文，但你只需要翻译标记为【需要翻译】的部分）：

"""

    def _create_monologue_output_requirements(self) -> str:
        """Create output requirements for monologue"""
        return """\n【输出要求 - 单人独白】

1. 只翻译【需要翻译】标记的部分
2. ⚠️ **只使用speaker_0**
3. ⚠️ **停顿标记必须使用**（核心要求）：
   - 关键观点前、数字前、转折前必须加 `……`
   - 列举时每点之间加 `……`
4. ⚠️ **口语化适度**：
   - 金句保持权威，不加口头禅
   - 话题过渡处可加串联词（每2-3段1次）
5. ⚠️ **数字必须强调**："整整90%！"、"不到15%！"
6. ⚠️ 完全不用情绪标记、重音标记
7. 直接输出翻译结果，不要添加任何说明或注释

开始翻译："""

    def _create_dialogue_output_requirements(self) -> str:
        """Create output requirements for dialogue"""
        return """\n【输出要求 - 对话】

1. 只翻译【需要翻译】标记的部分
2. ⚠️ **保护金句和强逻辑段落完整性**，不在中间插入回应
3. ⚠️ **简单回应处理**：
   - 省略：嗯、是的、对、好的、OK、Yeah、Right等
   - 保留：带情绪回应、引导性追问、超过5字的实质内容
4. ⚠️ **让嘉宾说完完整观点再切换speaker**
5. ⚠️ 完全不用情绪标记、重音标记
6. ⚠️ 停顿标记……在关键位置使用
7. 直接输出翻译结果，不要添加任何说明或注释

开始翻译："""

    def translate_segment(
        self,
        segments: List[Dict[str, Any]],
        segment_index: int,
        speaker_count: int = 2
    ) -> str:
        """
        Translate a single segment with context

        Args:
            segments: List of ASR segments
            segment_index: Index of the segment to translate
            speaker_count: Number of speakers (1=monologue, 2+=dialogue)
        """
        prompt = self._create_translation_prompt_v14(segments, segment_index, speaker_count)

        try:
            print(f"Translating segment {segment_index}...")
            translated = self._call_gemini_api(prompt).strip()
            print(f"Segment {segment_index} translated successfully")
            return translated

        except Exception as e:
            raise RuntimeError(f"Translation failed for segment {segment_index}: {str(e)}")

    def translate_all_segments(
        self,
        segments: List[Dict[str, Any]],
        delay_between_calls: float = 1.0,
        speaker_count: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Translate all segments with context preservation

        Args:
            segments: List of ASR segments
            delay_between_calls: Delay between API calls in seconds
            speaker_count: Number of speakers (1=monologue, 2+=dialogue)
        """
        print(f"Translating {len(segments)} segments (speaker_count={speaker_count})...")

        translations = []

        for i, segment in enumerate(segments):
            try:
                translated_text = self.translate_segment(segments, i, speaker_count)

                translation = {
                    "segment_id": segment.get("segment_id", i),
                    "start_time_ms": segment.get("start_time_ms"),
                    "end_time_ms": segment.get("end_time_ms"),
                    "original_text": segment.get("formatted_text", ""),
                    "translated_text": translated_text
                }

                translations.append(translation)

                # Rate limiting
                if i < len(segments) - 1:
                    time.sleep(delay_between_calls)

            except Exception as e:
                print(f"Error translating segment {i}: {e}")
                raise  # Fail fast

        print(f"All {len(translations)} segments translated successfully")
        return translations

    def save_translations(
        self,
        translations: List[Dict[str, Any]],
        output_path: Path,
        asr_file_path: Optional[Path] = None,
        podcast_name: Optional[str] = None
    ):
        """Save translations to JSON file with metadata for verification

        Args:
            translations: List of translation dictionaries
            output_path: Output JSON file path
            asr_file_path: Path to source ASR file (for hash verification)
            podcast_name: Name of the podcast (optional)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Compute ASR file hash for verification
        asr_hash = None
        if asr_file_path and asr_file_path.exists():
            with open(asr_file_path, 'rb') as f:
                asr_hash = hashlib.sha256(f.read()).hexdigest()[:16]  # First 16 chars

        result = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "asr_file": str(asr_file_path.name) if asr_file_path else None,
                "asr_hash": asr_hash,
                "podcast_name": podcast_name,
                "translator_version": "v1.5"
            },
            "total_segments": len(translations),
            "translations": translations
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Translations saved to: {output_path}")
        if asr_hash:
            print(f"  ASR hash: {asr_hash}")


if __name__ == "__main__":
    # Example usage
    import argparse
    from config import Config

    parser = argparse.ArgumentParser(description="Translate ASR segments v1.4")
    parser.add_argument("input_file", help="Input ASR JSON file")
    parser.add_argument("-o", "--output", help="Output translations JSON file")
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="Delay between API calls in seconds (default: 1.0)"
    )
    parser.add_argument(
        "-s", "--speakers",
        type=int,
        default=None,
        help="Number of speakers (auto-detect if not specified)"
    )

    args = parser.parse_args()

    Config.validate()

    # Load ASR data
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        segments = data["segments"]

    # Auto-detect speaker count if not specified
    if args.speakers is not None:
        speaker_count = args.speakers
    else:
        speaker_count = count_speakers(data)
    print(f"Speaker count: {speaker_count} ({'monologue' if speaker_count == 1 else 'dialogue'})")

    # Translate
    translator = GeminiTranslatorV14(api_key=Config.GEMINI_API_KEY)

    try:
        translations = translator.translate_all_segments(
            segments,
            delay_between_calls=args.delay,
            speaker_count=speaker_count
        )

        # Save
        if args.output:
            translator.save_translations(translations, Path(args.output))
        else:
            print(json.dumps(translations, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
