"""Gemini translation module v1.4 - Natural TTS with no emotion markers"""
import json
import time
import os
from pathlib import Path
from typing import List, Dict, Any
import requests


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

        print(f"✓ Using Gemini model: {model_name}")
        if self.proxies:
            print(f"✓ Using proxy: {self.proxies}")

    def _call_gemini_api(self, prompt: str) -> str:
        """
        Call Gemini API using REST endpoint
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

        # Retry logic for proxy connection issues
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    params=params,
                    proxies=self.proxies if self.proxies else None,
                    timeout=120
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

            except requests.exceptions.ProxyError as e:
                if attempt < max_retries - 1:
                    print(f"⚠ Proxy connection failed (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    continue
                else:
                    raise RuntimeError(f"API request failed after {max_retries} attempts: {str(e)}")

            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"API request failed: {str(e)}")

    def _create_translation_prompt_v14(
        self,
        segments: List[Dict[str, Any]],
        target_segment_index: int
    ) -> str:
        """
        Create translation prompt for v1.4 (no emotion markers)
        """
        # Get context window
        context_segments = []
        start_idx = max(0, target_segment_index - 1)
        end_idx = min(len(segments), target_segment_index + 2)

        for i in range(start_idx, end_idx):
            context_segments.append(segments[i])

        # Build v1.4 prompt
        prompt = f"""你是一个专业的播客翻译专家和对话脚本作家。请将以下英文对话翻译成极具真实感的中文播客对话。

【v1.4核心理念】：让TTS引擎像真人一样理解和表达情绪

这次翻译将使用Gemini 2.5 Pro TTS引擎，它具备强大的语义理解能力，能根据文本内容自动判断：
- 情绪表达（兴奋、好奇、强调、思考等）
- 重音位置（关键数据、核心概念）
- 语速变化（思考时慢、列举时快）
- 停顿节奏（句间、段落间）

因此，你的任务是：**写出最自然的中文对话文本，让TTS引擎自己理解情绪，而不是用标记告诉它**。

【第一层级：真实对话元素】✅ 保留并强化

1. **口头禅和填充词**（经常使用）：
   - 思考型："你知道"、"我的意思是"、"怎么说呢"、"应该说"、"这个问题呢"
   - 过渡型："像是"、"比如说"、"举个例子"、"说实话"
   - 确认型："对吧"、"是不是"、"明白吗"、"懂我意思吧"

2. **微观互动**（对话回应）：
   - 积极回应："哦真的吗？"、"是这样啊"、"原来如此"、"有意思"、"确实"
   - 强烈认同："对对对"、"没错"、"完全正确"、"太对了"
   - 惊讶/好奇："真的假的？"、"不会吧"、"居然"、"竟然"

3. **语气词**（⭐ v1.4新增）：
   - 愉快/笑声场景：自动添加"哈哈哈"、"哈哈"
   - 判断标准：
     * 说话人自嘲或幽默评论时
     * 惊讶但愉快的发现时
     * 调侃式的总结时
     * 反问后的轻松气氛时
   - 示例："从90%掉到10%，哈哈，这个变化太剧烈了！"
   - 示例："（笑）这是个非常有意思的话题。"

4. **思考性表达**：
   - "这个问题呢"、"我觉得吧"、"在我看来"、"要我说"
   - "其实仔细想想"、"说起来"、"谈到这个"

5. **口语化改写**：
   - 避免书面语，使用口语表达
   - 长句拆分成短句，符合说话节奏
   - 适当重复强调重点（"非常非常重要"、"真的真的"）

【第二层级：重音和停顿策略】⭐ v1.4简化版

**不用标记，用自然表达方式让TTS理解重音**：

1. **数字强调**（停顿 + 强调词组合）：
   - ❌ 不用：CPU的占比是**90%**（重读延长）
   - ✅ 改用：CPU的占比是……整整90%！
   - ✅ 改用：今年是多少？不到15%！
   - ✅ 改用：从……90%……直接掉到了……10%！

2. **核心概念强调**（用自然强调词）：
   - ❌ 不用：**摩尔定律**（重读延长）
   - ✅ 改用：就是摩尔定律
   - ✅ 改用：这个摩尔定律
   - ✅ 改用：所谓的第一性原理

3. **停顿标记**（保留，但更自然）：
   - 思考停顿：……
   - 列举停顿：用顿号、逗号自然分隔
   - 强调停顿：在关键数字、概念前后用……

4. **语速自然变化**（不标记，让TTS理解）：
   - 思考时：文本本身就会慢（"我记得六年前……"）
   - 兴奋时：文本本身就会快（短句、感叹号）
   - 列举时：文本结构决定（"不管是银行业、还是信用卡行业……"）

【角色识别和风格】

- **主持人/提问者**：多用反问、疑问句，语调有变化
- **专家/讲解者**：多用"你知道"、"我的意思是"，自然引导
- **讨论者**：多用"我觉得吧"、"在我看来"

【输出格式】⭐ v1.4新格式

⚠️ **重要限制: 只使用speaker_0和speaker_1 (TTS API限制)**

使用speaker_X格式（不是[X]），并且**只能使用speaker_0和speaker_1**：

```
speaker_0: 我们会不会迎来一个所谓的AI泡沫？
speaker_1: 那我跟您聊聊我们看到的情况吧。
speaker_0: 好的。
speaker_1: 所以我觉得吧，你要想看懂现在全世界到底在发生什么……
```

**Speaker分配规则:**
- speaker_0: 主持人/提问者 (女声)
- speaker_1: 嘉宾/回答者 (男声)
- ⚠️ 禁止使用speaker_2, speaker_3等 - TTS只支持2个声音!

【翻译原则 v1.4】

1. ✅ **只使用speaker_0和speaker_1** (绝对不能有speaker_2, speaker_3等)
2. ✅ 使用speaker_X格式（不是[X]:）
3. ✅ 完全不用情绪标记，让文本自己表达情绪
4. ✅ 完全不用 **词语**（重读延长），用停顿+强调词代替
5. ✅ 保留停顿标记……（在关键位置）
6. ✅ 保持自然对话元素（口头禅、互动、语气词）
7. ✅ 长句拆分，一个观点3-5个短句
8. ✅ 适当添加语气词"哈哈哈"等（判断愉快场景）
9. ✅ 用自然语言表达重音（停顿+强调词："整整90%"）

【示例对比】

❌ v1.3A版本（有标记）：
"[特别强调！音量加重！语速放慢！] 你猜今年是多少？……
[非常兴奋！音量提高！语速稍快！] **不到15%**（重读延长）！……"

✅ v1.4版本（无标记）：
"speaker_1: 你猜今年是多少？不到15%！
speaker_1: 基本上就是从……90%……直接掉到了……10%！"

以下是对话内容（包含上下文，但你只需要翻译标记为【需要翻译】的部分）：

"""

        for i, seg in enumerate(context_segments):
            segment_idx = start_idx + i
            formatted_text = seg.get("formatted_text", "")

            if segment_idx == target_segment_index:
                prompt += f"\n【需要翻译 - Segment {segment_idx}】:\n{formatted_text}\n"
            else:
                prompt += f"\n【上下文 - Segment {segment_idx}】:\n{formatted_text}\n"

        prompt += """\n【输出要求 v1.4】

1. 只翻译【需要翻译】标记的部分
2. ⚠️ **只使用speaker_0和speaker_1** (绝对不能有speaker_2, speaker_3等)
3. 使用speaker_X格式（如speaker_0:、speaker_1:）
4. ⚠️ 完全不用情绪标记、重音标记
5. ⚠️ 用自然语言表达重音（停顿+强调词:"整整90%"、"就是摩尔定律"）
6. ⚠️ 适当保留停顿标记……（关键位置）
7. ⚠️ 愉快/笑声场景自动添加"哈哈哈"、"（笑）"等语气词
8. 确保添加了足够的自然对话元素（口头禅、互动）
8. 每句话都符合真人说话的节奏
9. 直接输出翻译结果，不要添加任何说明或注释

开始翻译："""

        return prompt

    def translate_segment(
        self,
        segments: List[Dict[str, Any]],
        segment_index: int
    ) -> str:
        """
        Translate a single segment with context
        """
        prompt = self._create_translation_prompt_v14(segments, segment_index)

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
        delay_between_calls: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Translate all segments with context preservation
        """
        print(f"Translating {len(segments)} segments...")

        translations = []

        for i, segment in enumerate(segments):
            try:
                translated_text = self.translate_segment(segments, i)

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

    def save_translations(self, translations: List[Dict[str, Any]], output_path: Path):
        """Save translations to JSON file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = {
            "total_segments": len(translations),
            "translations": translations
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"Translations saved to: {output_path}")


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

    args = parser.parse_args()

    Config.validate()

    # Load ASR segments
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        segments = data["segments"]

    # Translate
    translator = GeminiTranslatorV14(api_key=Config.GEMINI_API_KEY)

    try:
        translations = translator.translate_all_segments(
            segments,
            delay_between_calls=args.delay
        )

        # Save
        if args.output:
            translator.save_translations(translations, Path(args.output))
        else:
            print(json.dumps(translations, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
