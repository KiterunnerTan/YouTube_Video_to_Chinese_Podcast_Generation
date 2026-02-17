"""TTS Segment Optimizer - 使用大模型优化翻译结果的TTS分段"""
import re
import time
import os
from typing import List, Dict, Any, Tuple
import requests


class TTSSegmentOptimizer:
    """使用Gemini API优化TTS分段，提升听感体验"""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """
        初始化TTS分段优化器

        Args:
            api_key: Gemini API key
            model_name: 使用的模型名称（默认使用flash版本以节省成本）
        """
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

        # 从环境变量设置代理
        self.proxies = {}
        if os.getenv('HTTP_PROXY'):
            self.proxies['http'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            self.proxies['https'] = os.getenv('HTTPS_PROXY')

        print(f"[TTSSegmentOptimizer] Using model: {model_name}")
        if self.proxies:
            print(f"[TTSSegmentOptimizer] Using proxy: {self.proxies}")

    def _call_gemini_api(self, prompt: str) -> str:
        """
        调用Gemini API

        Args:
            prompt: 提示词

        Returns:
            API响应文本
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

        # 重试逻辑
        max_retries = 3
        retry_delays = [5, 10, 15]

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

                # 提取响应文本
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
                requests.exceptions.SSLError,
                requests.exceptions.ProxyError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout
            ) as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"[TTSSegmentOptimizer] Network error (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                    print(f"  Error type: {type(e).__name__}")
                    time.sleep(delay)
                    continue
                else:
                    raise RuntimeError(f"API request failed after {max_retries} retries: {str(e)}")

            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"API request failed: {str(e)}")

    def _create_optimization_prompt(self, translated_text: str) -> str:
        """
        创建分段优化的提示词

        Args:
            translated_text: 翻译后的文本（speaker_X: 内容 格式）

        Returns:
            优化提示词
        """
        prompt = """你是一个专业的播客音频制作专家。请对以下翻译后的播客对话进行TTS分段优化，提升听感体验。

【输入格式】
翻译后的对话文本，格式为：
speaker_X: 内容

【优化规则】

1. **合并连续同speaker发言**：
   - 如果同一个speaker连续说了多句，合并成一段
   - 用句号连接，保持语义完整
   - 示例：
     ```
     原始：
     speaker_1: 我们用了一个新方法。
     speaker_1: 效果非常好。

     优化后：
     [SEG_1]
     speaker_1: 我们用了一个新方法。效果非常好。
     [/SEG_1]
     ```

2. **标记省略的简单回应[SKIP]**：
   - 以下类型的简单回应应标记为[SKIP]：
     - 单字回应：嗯、哦、啊、对、好、是
     - 简单确认：是的、对的、好的、没错、确实、明白、了解
     - 简单附和：真的吗、是吗、哦真的、原来如此
   - 注意：如果回应后面紧跟实质内容，不要标记为SKIP
   - 示例：
     ```
     [SKIP]
     speaker_0: 嗯
     [/SKIP]

     [SKIP]
     speaker_1: 是的
     [/SKIP]
     ```

   ⚠️ **绝对不能标记为SKIP的内容**：
   - 开场语/欢迎语："大家好"、"欢迎收听"、"今天我们的嘉宾是..."
   - 嘉宾介绍：介绍嘉宾身份、背景的内容
   - 结尾语："感谢收听"、"下期再见"
   - 超过10个字的实质内容
   - 带情绪的回应："哇，太厉害了！"、"这个变化也太大了！"

3. **智能分段（150字限制）**：
   - 单段内容超过150字时，在句号处拆分
   - 拆分时保持语义完整，不要在句子中间断开
   - 每个分段用[SEG_N]标记
   - 示例：
     ```
     [SEG_1]
     speaker_1: 第一部分内容...（约100-150字）
     [/SEG_1]

     [SEG_2]
     speaker_1: 第二部分内容...（约100-150字）
     [/SEG_2]
     ```

4. **保持停顿位置自然**：
   - 在关键观点前后保留自然停顿
   - 不要在强调词或数字前断开

【输出格式要求】

严格按照以下格式输出，不要添加任何说明或注释：

```
[SEG_1]
speaker_X: 内容
[/SEG_1]

[SKIP]
speaker_Y: 简单回应
[/SKIP]

[SEG_2]
speaker_Z: 内容
[/SEG_2]
```

【注意事项】
- 每个[SEG_N]或[SKIP]块只包含一个speaker的内容
- SEG编号从1开始，按顺序递增
- SKIP块不需要编号
- 保持原文的speaker标识（speaker_0, speaker_1等）
- 不要修改原文内容，只做分段和标记
- ⚠️ 开场语、嘉宾介绍、结尾语必须保留，不能标记为SKIP

【待优化的文本】

"""
        prompt += translated_text
        prompt += "\n\n【开始优化】"

        return prompt

    def optimize_segments(self, translated_text: str) -> str:
        """
        优化翻译后的文本分段

        Args:
            translated_text: 翻译后的文本（speaker_X: 内容 格式）

        Returns:
            优化后的分段文本，包含[SEG_N]和[SKIP]标记
        """
        prompt = self._create_optimization_prompt(translated_text)

        try:
            print("[TTSSegmentOptimizer] Optimizing segments...")
            optimized = self._call_gemini_api(prompt).strip()
            print("[TTSSegmentOptimizer] Optimization completed")
            return optimized

        except Exception as e:
            raise RuntimeError(f"Segment optimization failed: {str(e)}")

    def optimize_translation_result(
        self,
        translations: List[Dict[str, Any]],
        delay_between_calls: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        优化整个翻译结果

        Args:
            translations: 翻译结果列表，每个元素包含translated_text字段
            delay_between_calls: API调用间隔（秒）

        Returns:
            添加了optimized_text字段的翻译结果列表
        """
        print(f"[TTSSegmentOptimizer] Optimizing {len(translations)} segments...")

        for i, translation in enumerate(translations):
            translated_text = translation.get("translated_text", "")

            if not translated_text:
                print(f"[TTSSegmentOptimizer] Segment {i}: empty, skipping")
                translation["optimized_text"] = ""
                continue

            try:
                optimized = self.optimize_segments(translated_text)
                translation["optimized_text"] = optimized
                print(f"[TTSSegmentOptimizer] Segment {i}: optimized")

                # Rate limiting
                if i < len(translations) - 1:
                    time.sleep(delay_between_calls)

            except Exception as e:
                print(f"[TTSSegmentOptimizer] Segment {i}: optimization failed - {e}")
                # 失败时保留原文
                translation["optimized_text"] = translated_text

        print(f"[TTSSegmentOptimizer] All {len(translations)} segments processed")
        return translations


def parse_optimized_segments(text: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    解析优化后的文本，提取分段和跳过的内容

    Args:
        text: 优化后的文本，包含[SEG_N]和[SKIP]标记

    Returns:
        Tuple containing:
        - segments: 分段列表，每个元素为 {"speaker": "speaker_X", "content": "..."}
        - skipped: 被跳过的简单回应列表
    """
    segments = []
    skipped = []

    # 匹配[SEG_N]块
    seg_pattern = r'\[SEG_\d+\]\s*(speaker_\d+):\s*(.*?)\s*\[/SEG_\d+\]'
    seg_matches = re.findall(seg_pattern, text, re.DOTALL)

    for speaker, content in seg_matches:
        content = content.strip()
        if content:
            segments.append({
                "speaker": speaker,
                "content": content
            })

    # 匹配[SKIP]块
    skip_pattern = r'\[SKIP\]\s*speaker_\d+:\s*(.*?)\s*\[/SKIP\]'
    skip_matches = re.findall(skip_pattern, text, re.DOTALL)

    for content in skip_matches:
        content = content.strip()
        if content:
            skipped.append(content)

    return segments, skipped


def parse_optimized_segments_with_order(text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    解析优化后的文本，保持原始顺序（包括SKIP的位置信息）

    Args:
        text: 优化后的文本，包含[SEG_N]和[SKIP]标记

    Returns:
        Tuple containing:
        - segments: 分段列表，每个元素为 {"speaker": "speaker_X", "content": "...", "type": "seg"|"skip"}
        - skipped: 被跳过的简单回应列表
    """
    segments = []
    skipped = []

    # 匹配所有块（SEG和SKIP），保持顺序
    all_pattern = r'(\[SEG_\d+\]|\[SKIP\])(.*?)(\[/SEG_\d+\]|\[/SKIP\])'
    matches = re.finditer(all_pattern, text, re.DOTALL)

    for match in matches:
        tag_start = match.group(1)
        content = match.group(2).strip()

        # 解析speaker和内容
        speaker_match = re.match(r'(speaker_\d+):\s*(.*)', content, re.DOTALL)
        if speaker_match:
            speaker = speaker_match.group(1)
            text_content = speaker_match.group(2).strip()

            if '[SEG_' in tag_start:
                segments.append({
                    "speaker": speaker,
                    "content": text_content,
                    "type": "seg"
                })
            else:  # SKIP
                segments.append({
                    "speaker": speaker,
                    "content": text_content,
                    "type": "skip"
                })
                skipped.append(text_content)

    return segments, skipped


if __name__ == "__main__":
    # 示例用法
    import argparse
    import json
    import sys
    sys.path.insert(0, str(__file__).rsplit('/', 2)[0])
    from config import Config

    parser = argparse.ArgumentParser(description="TTS Segment Optimizer")
    parser.add_argument("input_file", help="Input translations JSON file")
    parser.add_argument("-o", "--output", help="Output optimized JSON file")
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="Delay between API calls in seconds (default: 1.0)"
    )

    args = parser.parse_args()

    Config.validate()
    Config.setup_proxy()

    # 加载翻译结果
    with open(args.input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        translations = data.get("translations", [])

    # 优化
    optimizer = TTSSegmentOptimizer(api_key=Config.GEMINI_API_KEY)

    try:
        optimized_translations = optimizer.optimize_translation_result(
            translations,
            delay_between_calls=args.delay
        )

        # 保存结果
        if args.output:
            output_data = {
                "metadata": data.get("metadata", {}),
                "total_segments": len(optimized_translations),
                "translations": optimized_translations
            }
            output_data["metadata"]["optimizer_version"] = "v1.0"

            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"Optimized translations saved to: {args.output}")
        else:
            # 打印解析结果示例
            for i, trans in enumerate(optimized_translations[:2]):
                print(f"\n=== Segment {i} ===")
                optimized_text = trans.get("optimized_text", "")
                if optimized_text:
                    segments, skipped = parse_optimized_segments(optimized_text)
                    print(f"Segments: {len(segments)}")
                    for seg in segments:
                        print(f"  {seg['speaker']}: {seg['content'][:50]}...")
                    print(f"Skipped: {skipped}")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)
