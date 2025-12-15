"""Gemini translation module with batch processing and context preservation"""
import json
import time
import os
from pathlib import Path
from typing import List, Dict, Any
import requests


class GeminiTranslator:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-pro"):
        """
        Initialize Gemini translator using REST API

        Args:
            api_key: Gemini API key
            model_name: Model to use for translation (e.g., gemini-2.0-flash-exp, gemini-1.5-pro)
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

        Args:
            prompt: The prompt to send

        Returns:
            Generated text response

        Raises:
            RuntimeError: If API call fails
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

    def _create_translation_prompt(
        self,
        segments: List[Dict[str, Any]],
        target_segment_index: int
    ) -> str:
        """
        Create translation prompt with context

        Args:
            segments: All segments (for context)
            target_segment_index: Index of the segment to translate

        Returns:
            Prompt with context
        """
        # Get context window (previous and next segments)
        context_segments = []
        start_idx = max(0, target_segment_index - 1)
        end_idx = min(len(segments), target_segment_index + 2)

        for i in range(start_idx, end_idx):
            context_segments.append(segments[i])

        # Build prompt
        prompt = f"""你是一个专业的播客翻译专家和对话脚本作家。请将以下英文对话翻译成极具真实感的中文播客对话。

核心目标：让听众感觉这是两个真人在自然交谈，而不是在朗读翻译稿。

【第一层级：语义层面的自然对话元素】

1. **口头禅和填充词**（经常使用）：
   - 思考型："你知道"、"我的意思是"、"怎么说呢"、"让我想想"、"应该说"
   - 过渡型："像是"、"比如说"、"举个例子"、"说实话"、"老实讲"
   - 确认型："对吧"、"是不是"、"明白吗"、"懂我意思吧"

2. **微观互动**（对话回应）：
   - 积极回应："哦真的吗？"、"是这样啊"、"原来如此"、"有意思"、"确实"
   - 强烈认同："对对对"、"没错"、"完全正确"、"太对了"、"就是这样"
   - 惊讶/好奇："真的假的？"、"不会吧"、"居然"、"竟然"

3. **思考性表达**（表现思考过程）：
   - "这个问题呢"、"我觉得吧"、"在我看来"、"要我说"、"如果非要说的话"
   - "其实仔细想想"、"说起来"、"谈到这个"

4. **情绪和节奏标记**：
   - 重要观点前："这很重要"、"关键是"、"重点来了"
   - 总结时："总的来说"、"归根结底"、"简单来讲"
   - 转折时："但是话说回来"、"不过呢"、"换个角度看"

5. **口语化改写**：
   - 避免书面语，使用口语表达
   - 长句拆分成短句，符合说话节奏
   - 适当重复强调重点（"非常非常重要"、"真的真的"）

6. **停顿提示**（用标点表达）：
   - 思考停顿：用"……"表示
   - 强调停顿：用"，"或"。"隔开关键词
   - 列举停顿：每项之间用明确的停顿

【角色识别和风格调整】

- **主持人/提问者**：多用引导语（"那么接下来"、"我们来看看"、"这就有意思了"）
- **专家/讲解者**：多用解释语（"实际上"、"准确地说"、"从技术角度"）
- **讨论者**：多用互动语（"你觉得呢"、"我同意你的观点"、"这点我有不同看法"）

【翻译原则】

1. ⚠️ 不要逐字翻译，要意译成自然对话
2. ⚠️ 每2-3句话就添加1-2个自然元素（口头禅、互动等）
3. ⚠️ 保持说话人的个性差异（有的人话多，有的人简洁）
4. ⚠️ 长句必须拆分，一个完整观点用3-5个短句表达
5. ⚠️ 问答要有互动感，不能像机器人对话

【示例对比】

❌ 差的翻译："人工智能的发展速度很快，它正在改变我们的生活方式。"

✅ 好的翻译："你知道吗，人工智能发展得真的是太快了。像是……怎么说呢，它现在已经在方方面面改变着我们的生活。真的，这个变化速度是惊人的。"

以下是对话内容（包含上下文，但你只需要翻译标记为【需要翻译】的部分）：

"""

        for i, seg in enumerate(context_segments):
            segment_idx = start_idx + i
            formatted_text = seg.get("formatted_text", "")

            if segment_idx == target_segment_index:
                prompt += f"\n【需要翻译 - Segment {segment_idx}】:\n{formatted_text}\n"
            else:
                prompt += f"\n【上下文 - Segment {segment_idx}】:\n{formatted_text}\n"

        prompt += """\n【输出要求】

1. 只翻译【需要翻译】标记的部分
2. 保持原有的说话人标记格式：[speaker]: 翻译内容
3. 直接输出翻译结果，不要添加任何说明或注释
4. 确保添加了足够的自然对话元素（口头禅、互动、停顿等）
5. 每句话都要符合真人说话的节奏和方式

开始翻译："""

        return prompt

    def translate_segment(
        self,
        segments: List[Dict[str, Any]],
        segment_index: int
    ) -> str:
        """
        Translate a single segment with context

        Args:
            segments: All segments
            segment_index: Index of segment to translate

        Returns:
            Translated text

        Raises:
            RuntimeError: If translation fails
        """
        prompt = self._create_translation_prompt(segments, segment_index)

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

        Args:
            segments: List of segments to translate
            delay_between_calls: Delay between API calls (to avoid rate limits)

        Returns:
            List of segments with translations
        """
        print(f"Translating {len(segments)} segments...")

        translated_segments = []

        for i, segment in enumerate(segments):
            try:
                translation = self.translate_segment(segments, i)

                translated_segment = {
                    "segment_id": segment["segment_id"],
                    "start_time_ms": segment["start_time_ms"],
                    "end_time_ms": segment["end_time_ms"],
                    "original_text": segment["formatted_text"],
                    "translated_text": translation
                }

                translated_segments.append(translated_segment)

                # Rate limiting
                if i < len(segments) - 1:
                    time.sleep(delay_between_calls)

            except Exception as e:
                print(f"Error translating segment {i}: {e}")
                raise  # Fail fast as per requirements

        print(f"All {len(segments)} segments translated successfully")
        return translated_segments

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

    parser = argparse.ArgumentParser(description="Translate segments using Gemini")
    parser.add_argument("input_file", help="Input processed segments JSON file")
    parser.add_argument("-o", "--output", help="Output translations JSON file")
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="Delay between API calls in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    Config.validate()

    # Load processed segments
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        segments = data["segments"]

    # Translate
    translator = GeminiTranslator(api_key=Config.GEMINI_API_KEY)

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
