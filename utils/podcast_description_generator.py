"""播客节目文案生成器 - 使用Gemini生成专业播客介绍

v2.6更新：
- 修复AI编造时间戳的问题
- 添加时间戳比例换算功能（考虑开场白/概要偏移）
- 时间戳上限检查，防止超出原视频时长

v2.5更新：
- 两阶段智能提取：先提取核心话题，再匹配准确时间戳
- "您将了解到"：3-4个问句形式，无时间戳，无小标题
- "时点内容"：6-8个话题，带时间戳和小标题，覆盖全部内容
"""
import requests
import json
import os
import re
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple


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

    @staticmethod
    def get_audio_duration(audio_path: str) -> float:
        """获取音频文件时长（秒）"""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"⚠️ 获取音频时长失败: {e}")
            return 0.0

    @staticmethod
    def ms_to_timestamp(ms: int) -> str:
        """毫秒转时间戳格式 [MM:SS] 或 [H:MM:SS]"""
        total_seconds = ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"[{hours}:{minutes:02d}:{seconds:02d}]"
        else:
            return f"[{minutes:02d}:{seconds:02d}]"

    @staticmethod
    def timestamp_to_ms(timestamp: str) -> int:
        """时间戳格式 [MM:SS] 或 [H:MM:SS] 转毫秒"""
        # 先尝试匹配 [H:MM:SS] 格式
        match = re.match(r'\[(\d+):(\d+):(\d+)\]', timestamp)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            return (hours * 3600 + minutes * 60 + seconds) * 1000

        # 再尝试匹配 [MM:SS] 格式
        match = re.match(r'\[(\d+):(\d+)\]', timestamp)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            return (minutes * 60 + seconds) * 1000
        return 0

    def convert_timestamps_for_podcast(
        self,
        topics_with_timestamps: List[Dict],
        original_video_duration_ms: int,
        main_audio_duration_ms: int,
        prologue_duration_ms: int = 0,
        summary_duration_ms: int = 0,
        music_intro_duration_ms: int = 5000,
        music_transition_duration_ms: int = 3000
    ) -> List[Dict]:
        """
        按比例换算时间戳，并加上开场白/概要/音乐的偏移

        播客结构：
        music_1 → 开场白 → music_2 → 概要 → music_2 → 主音频 → music_1

        Args:
            topics_with_timestamps: 带时间戳的话题列表
            original_video_duration_ms: 原视频总时长（毫秒）
            main_audio_duration_ms: 主音频时长（毫秒）
            prologue_duration_ms: 开场白时长（毫秒）
            summary_duration_ms: 概要时长（毫秒）
            music_intro_duration_ms: 片头音乐时长（毫秒）
            music_transition_duration_ms: 过渡音乐时长（毫秒）

        Returns:
            换算后的话题列表
        """
        if original_video_duration_ms <= 0 or main_audio_duration_ms <= 0:
            return topics_with_timestamps

        # 计算比例
        ratio = main_audio_duration_ms / original_video_duration_ms

        # 计算偏移量（主音频之前的所有内容）
        # 结构：music_1 → 开场白 → music_2 → 概要 → music_2 → 主音频
        offset_ms = (
            music_intro_duration_ms +      # 片头音乐
            prologue_duration_ms +          # 开场白
            music_transition_duration_ms +  # 过渡音乐1
            summary_duration_ms +           # 概要
            music_transition_duration_ms    # 过渡音乐2
        )

        print(f"\n📊 时间戳换算:")
        print(f"  原视频时长: {original_video_duration_ms // 60000}:{(original_video_duration_ms % 60000) // 1000:02d}")
        print(f"  主音频时长: {main_audio_duration_ms // 60000}:{(main_audio_duration_ms % 60000) // 1000:02d}")
        print(f"  换算比例: {ratio:.2f}")
        print(f"  偏移量: {offset_ms // 1000}秒")

        converted_topics = []
        for topic in topics_with_timestamps:
            original_ts = topic.get('timestamp', '[00:00]')
            original_ms = self.timestamp_to_ms(original_ts)

            # 检查是否超出原视频时长
            if original_ms > original_video_duration_ms:
                print(f"  ⚠️ {original_ts} 超出原视频时长，截断到结尾")
                original_ms = original_video_duration_ms

            # 按比例换算主音频中的位置
            scaled_time_ms = int(original_ms * ratio)

            # 最终时间戳 = 偏移量 + 换算后的主音频位置
            final_time_ms = offset_ms + scaled_time_ms

            new_ts = self.ms_to_timestamp(final_time_ms)

            converted_topic = topic.copy()
            converted_topic['timestamp'] = new_ts
            converted_topics.append(converted_topic)

            print(f"  {original_ts} → {new_ts}")

        return converted_topics

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
                if 'transcription' in segment and segment['transcription'] and 'sentence' in segment['transcription']:
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

        return full_transcript

    def load_asr_transcript_with_timestamps(self, asr_file: Path) -> str:
        """
        加载带时间戳的ASR文字稿

        Args:
            asr_file: ASR结果JSON文件路径

        Returns:
            带时间戳的文字稿文本，格式如 "[00:00] 内容..."
        """
        with open(asr_file, 'r', encoding='utf-8') as f:
            asr_data = json.load(f)

        timestamped_transcript = ""

        if 'segments' in asr_data:
            for segment in asr_data['segments']:
                # 获取 segment 开始时间（毫秒转分:秒）
                start_ms = segment.get('start_time_ms', 0)
                minutes = start_ms // 60000
                seconds = (start_ms % 60000) // 1000
                timestamp = f"[{minutes:02d}:{seconds:02d}]"

                segment_text = ""
                # 格式1: transcription.sentence 结构（Qwen3 ASR）
                if 'transcription' in segment and segment['transcription'] and 'sentence' in segment['transcription']:
                    for sentence in segment['transcription']['sentence']:
                        segment_text += sentence.get('text', '') + " "
                # 格式2: items 结构
                elif 'items' in segment:
                    for item in segment['items']:
                        segment_text += item.get('text', '') + " "
                # 格式3: 直接 text 字段
                elif 'text' in segment:
                    segment_text = segment.get('text', '')

                if segment_text.strip():
                    timestamped_transcript += f"{timestamp} {segment_text.strip()}\n\n"

        return timestamped_transcript

    def load_translation_segments(self, asr_file: Path) -> List[Dict]:
        """
        加载翻译结果（带时间戳）

        优先从翻译缓存文件加载，否则从ASR文件加载

        Args:
            asr_file: ASR结果JSON文件路径

        Returns:
            翻译段落列表，每个包含 start_time_ms, end_time_ms, translated_text
        """
        # 尝试从翻译缓存加载（更准确，包含中文翻译）
        asr_basename = asr_file.stem
        translations_file = Path(f"output/translations/{asr_basename}_translations_enhanced.json")
        optimized_file = Path(f"output/translations/{asr_basename}_optimized.json")

        # 优先使用优化后的翻译
        if optimized_file.exists():
            with open(optimized_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            segments = data.get('translations', [])
            if segments:
                print(f"✓ 加载优化翻译文件: {optimized_file.name}")
                return segments

        # 其次使用基础翻译
        if translations_file.exists():
            with open(translations_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            segments = data.get('translations', [])
            if segments:
                print(f"✓ 加载翻译文件: {translations_file.name}")
                return segments

        # 最后从ASR文件构建
        print(f"⚠️ 未找到翻译文件，从ASR文件加载")
        with open(asr_file, 'r', encoding='utf-8') as f:
            asr_data = json.load(f)

        segments = []
        for segment in asr_data.get('segments', []):
            text = ""
            if 'transcription' in segment and segment['transcription'] and 'sentence' in segment['transcription']:
                for sentence in segment['transcription']['sentence']:
                    text += sentence.get('text', '') + " "
            elif 'text' in segment:
                text = segment.get('text', '')

            if text.strip():
                segments.append({
                    'start_time_ms': segment.get('start_time_ms', 0),
                    'end_time_ms': segment.get('end_time_ms', 0),
                    'translated_text': text.strip()
                })

        return segments

    def extract_core_topics(
        self,
        podcast_name: str,
        guest_name: str,
        translation_segments: List[Dict]
    ) -> Tuple[List[Dict], List[str]]:
        """
        阶段1：从完整翻译中提取核心话题和营销问题

        Args:
            podcast_name: 播客名称
            guest_name: 嘉宾名称
            translation_segments: 翻译段落列表

        Returns:
            (核心话题列表, 营销问题列表)
            核心话题格式: [{"title": "标题", "description": "描述", "key_sentence": "可搜索的关键句"}]
            营销问题格式: ["问句1", "问句2", ...]
        """
        print(f"\n{'='*60}")
        print(f"阶段1: 提取核心话题和营销问题")
        print(f"{'='*60}")

        # 构建完整文字稿（带时间标记，供模型参考）
        full_transcript = ""
        for seg in translation_segments:
            start_ms = seg.get('start_time_ms', 0)
            minutes = start_ms // 60000
            seconds = (start_ms % 60000) // 1000
            text = seg.get('translated_text', seg.get('optimized_text', ''))
            full_transcript += f"[{minutes:02d}:{seconds:02d}] {text}\n\n"

        print(f"✓ 完整文字稿长度: {len(full_transcript)} 字符")

        prompt = f"""你是一位资深播客内容分析专家。请分析以下播客访谈，提取核心内容。

**播客名称**：{podcast_name}
**嘉宾**：{guest_name}

**完整文字稿**：
{full_transcript}

**任务1：提取6-8个核心话题**（用于"时点内容"导航目录）

要求：
- 每个话题必须是节目中的重要内容点
- 话题应该均匀分布在整个节目中（不能都集中在前半段）
- 每个话题提供一个"关键句"，这个句子必须是文字稿中实际出现的原文片段（用于后续时间戳匹配）
- **标题格式**：4-10字的名词短语，简洁概括主题，如"使命驱动的回归"、"指数级增长轨迹"、"编程的终结"
- **描述要求**：60-100字，忠实呈现嘉宾的行为和观点，结构如下：
  - [嘉宾名] + [行为动词] + [事实/经历]，并[行为动词2] + [嘉宾的观点/金句]
  - 行为动词：报告称、透露、分享了、回顾了、指出、强调、认为、预测、将...比作
  - 用引号突出嘉宾金句
  - 不要添加主观解读（如"这揭示了"、"这表明"）

**任务2：生成3-4个营销问题**（用于"您将了解到"部分）

要求：
- 用疑问句形式，引发读者好奇心
- 不要带时间戳
- 不要带小标题
- 聚焦核心价值和悬念

**输出格式（严格遵守JSON格式）**：

```json
{{
  "topics": [
    {{
      "title": "小标题（4-10字名词短语）",
      "description": "描述（60-100字，嘉宾名+行为动词+事实+观点）",
      "key_sentence": "文字稿中的原文片段（用于时间戳匹配，15-50字）"
    }}
  ],
  "marketing_questions": [
    "问句1？",
    "问句2？",
    "问句3？"
  ]
}}
```

**描述示例**：
- ✅ 好："切尔尼回顾了他在Cursor短暂两周后即重返Anthropic的经历，并指出'安全使命'是驱动他在AI领域工作的核心心理动力。"
- ✅ 好："切尔尼透露，自2024年11月起他100%的代码由Claude Code编写，日均提交10-30个PR，并强调这让他能将精力集中于高层架构设计而非语法细节。"
- ❌ 差："Boris分享了他的编程经历。"（太笼统，缺乏具体内容）
- ❌ 差："这揭示了AI领域顶尖人才的深层驱动力。"（不要添加主观解读）

请直接输出JSON，不要输出其他内容。"""

        url = f"{self.base_url}/gemini-2.5-pro:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.95,
                "maxOutputTokens": 16384
            }
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"⏳ 重试 {attempt}/{max_retries-1}...")
                    time.sleep(5)

                print("正在调用Gemini API提取核心话题...")

                response = requests.post(
                    url,
                    json=payload,
                    proxies=self.proxies,
                    timeout=120
                )

                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and len(result['candidates']) > 0:
                        text = result['candidates'][0]['content']['parts'][0].get('text', '')

                        # 提取JSON部分
                        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(1)
                        else:
                            # 尝试直接解析
                            json_str = text.strip()

                        try:
                            data = json.loads(json_str)
                            topics = data.get('topics', [])
                            questions = data.get('marketing_questions', [])

                            print(f"✓ 提取到 {len(topics)} 个核心话题")
                            print(f"✓ 提取到 {len(questions)} 个营销问题")

                            return topics, questions
                        except json.JSONDecodeError as e:
                            print(f"⚠️ JSON解析失败: {e}")
                            print(f"原始响应: {text[:500]}")

                print(f"❌ API调用失败: {response.status_code}")

            except Exception as e:
                print(f"❌ 提取失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")

        return [], []

    def match_timestamps(
        self,
        topics: List[Dict],
        translation_segments: List[Dict]
    ) -> List[Dict]:
        """
        阶段2：为每个话题匹配准确的时间戳（优化版）

        Args:
            topics: 核心话题列表（包含key_sentence）
            translation_segments: 翻译段落列表（包含时间戳）

        Returns:
            带时间戳的话题列表，按时间顺序排列，无重复时间戳
        """
        print(f"\n{'='*60}")
        print(f"阶段2: 匹配时间戳")
        print(f"{'='*60}")

        # 构建全文索引（用于模糊匹配）
        full_text_with_time = []
        for seg in translation_segments:
            start_ms = seg.get('start_time_ms', 0)
            text = seg.get('translated_text', seg.get('optimized_text', ''))
            full_text_with_time.append({
                'start_ms': start_ms,
                'text': text
            })

        # 按时间排序
        full_text_with_time.sort(key=lambda x: x['start_ms'])

        # 获取总时长用于分布优化
        total_duration_ms = max([seg['start_ms'] for seg in full_text_with_time]) if full_text_with_time else 0

        topics_with_timestamps = []
        used_timestamps = set()  # 防止重复时间戳

        for i, topic in enumerate(topics):
            key_sentence = topic.get('key_sentence', '')
            best_match_time = 0
            best_match_score = 0.0

            # 在每个段落中搜索关键句
            for seg in full_text_with_time:
                seg_text = seg['text']
                current_time = seg['start_ms']

                # 精确匹配
                if key_sentence in seg_text:
                    best_match_time = current_time
                    best_match_score = 1.0  # 修复：使用1.0而不是100
                    break

                # 模糊匹配：计算关键词重叠度
                key_words = set(key_sentence.replace('，', ' ').replace('。', ' ').replace('、', ' ').split())
                seg_words = set(seg_text.replace('，', ' ').replace('。', ' ').replace('、', ' ').split())

                # 过滤掉过短的词
                key_words = {w for w in key_words if len(w) > 1}
                seg_words = {w for w in seg_words if len(w) > 1}

                if key_words:
                    overlap = len(key_words & seg_words) / len(key_words)
                    if overlap > best_match_score:
                        best_match_score = overlap
                        best_match_time = current_time

            # 如果匹配度太低，使用时间分布策略
            if best_match_score < 0.3 and total_duration_ms > 0:
                # 将话题均匀分布在时间轴上
                target_position = i / max(len(topics) - 1, 1)  # 0到1之间
                target_time_ms = int(total_duration_ms * target_position)

                # 找到最接近目标时间的段落
                closest_seg = min(full_text_with_time,
                                key=lambda x: abs(x['start_ms'] - target_time_ms))
                best_match_time = closest_seg['start_ms']
                best_match_score = 0.5  # 标记为分布匹配

            # 避免重复时间戳（限制调整范围，不超过总时长）
            original_time = best_match_time
            adjustment = 0
            max_adjustment = min(300000, total_duration_ms - original_time) if total_duration_ms > 0 else 300000
            while best_match_time in used_timestamps and adjustment < max_adjustment:
                adjustment += 30000  # 每次调整30秒
                best_match_time = original_time + adjustment

            # 确保时间戳不超过总时长
            if total_duration_ms > 0 and best_match_time > total_duration_ms:
                best_match_time = total_duration_ms
                print(f"  ⚠️ 时间戳超出范围，截断到 {total_duration_ms}ms")

            used_timestamps.add(best_match_time)

            # 转换时间格式（使用统一的方法，支持超过1小时）
            timestamp = self.ms_to_timestamp(best_match_time)

            topics_with_timestamps.append({
                'timestamp': timestamp,
                'title': topic.get('title', ''),
                'description': topic.get('description', ''),
                'match_score': best_match_score,
                'start_ms': best_match_time  # 用于排序
            })

            # 显示匹配结果
            match_type = "精确匹配" if best_match_score == 1.0 else \
                        "分布匹配" if best_match_score == 0.5 else "模糊匹配"
            print(f"  {timestamp} {topic.get('title', '')} (匹配度: {best_match_score:.0%}, {match_type})")

        # 按时间顺序排序
        topics_with_timestamps.sort(key=lambda x: x['start_ms'])

        # 移除临时字段
        for topic in topics_with_timestamps:
            topic.pop('start_ms', None)

        return topics_with_timestamps

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

        prompt = f"""你是顶尖自媒体运营专家，擅长撰写高点击率播客标题。

**任务**：为这期播客生成3个吸引力标题

**播客**：{podcast_name}
**嘉宾**：{guest_name}

**文字稿摘要**：
{transcript[:5000]}

**标题要求**：
1. 每个标题20-40字
2. 必须包含：数据/比例 + 嘉宾观点/金句
3. 结构参考：
   - 数据+观点：90%的人放弃新年计划，因为他们搞错了改变的顺序
   - 金句型："你还不是那个该成功的人" Dan Koe谈身份重塑
   - 悬念型：健身者不需要自律？Dan Koe揭示成功者的秘密

**输出格式**（严格遵守）：
标题1: [内容]
标题2: [内容]
标题3: [内容]"""

        # 使用 Pro 模型生成标题（更稳定，输出更完整）
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
                "temperature": 0.85,
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
                            titles_text = candidate['content']['parts'][0].get('text', '').strip()

                            # 调试输出原始响应
                            print(f"\n📝 Gemini原始响应:\n{titles_text}\n")

                            # 解析3个备选标题
                            import re
                            lines = titles_text.split('\n')
                            titles = []
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    continue
                                # 匹配多种格式：
                                # "标题1: xxx" 或 "标题1：xxx"
                                # "1. xxx" 或 "1、xxx" 或 "1: xxx"
                                # "**标题1**: xxx"
                                patterns = [
                                    r'^标题[1-3][:：]\s*(.+)$',
                                    r'^\*\*标题[1-3]\*\*[:：]?\s*(.+)$',
                                    r'^[1-3][.、:：]\s*(.+)$',
                                    r'^\[第[一二三]个标题[内容]?\]\s*(.+)$',
                                ]
                                for pattern in patterns:
                                    match = re.match(pattern, line)
                                    if match:
                                        title = match.group(1).strip()
                                        # 移除可能的引号和方括号
                                        title = title.strip('"').strip('"').strip("'").strip('[]')
                                        if len(title) >= 10:  # 确保标题有足够长度
                                            titles.append(title)
                                        break

                            if titles:
                                print(f"✓ 标题生成成功，共 {len(titles)} 个备选：")
                                for i, t in enumerate(titles, 1):
                                    print(f"  {i}. {t}")

                                # 使用第一个标题
                                title = titles[0]
                                print(f"\n✓ 选用标题: {title}\n")
                                return title
                            else:
                                # 如果解析失败，尝试提取第一行有意义的内容
                                for line in lines:
                                    line = line.strip()
                                    if line and len(line) >= 15 and not line.startswith('**') and not line.startswith('#'):
                                        title = line.strip('"').strip('"').strip("'")
                                        print(f"\n✓ 标题生成成功（备用解析）")
                                        print(f"✓ 标题: {title}\n")
                                        return title
                                # 最后的备选
                                title = lines[0].strip() if lines else titles_text
                                title = title.strip('"').strip('"').strip("'")
                                print(f"\n✓ 标题生成成功")
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
        video_url: Optional[str] = None,
        timestamped_transcript: Optional[str] = None,
        translation_segments: Optional[List[Dict]] = None,
        podcast_audio_info: Optional[Dict] = None
    ) -> Optional[str]:
        """
        生成专业的播客节目介绍文案（两阶段智能提取 + 时间戳换算）

        Args:
            podcast_name: 播客名称
            guest_name: 嘉宾名称
            transcript: ASR文字稿
            video_url: 原视频URL（可选）
            timestamped_transcript: 带时间戳的文字稿（已弃用，保留兼容）
            translation_segments: 翻译段落列表（用于两阶段提取）
            podcast_audio_info: 播客音频信息（可选），用于时间戳换算

        Returns:
            生成的文案，或None
        """
        # 先生成标题
        title = self.generate_title(podcast_name, guest_name, transcript)

        print(f"\n{'='*80}")
        print(f"生成播客节目介绍文案 (v2.6 时间戳换算)")
        print(f"{'='*80}")
        print(f"播客: {podcast_name}")
        print(f"嘉宾: {guest_name}\n")

        # ========== 两阶段智能提取 ==========
        topics_with_timestamps = []
        marketing_questions = []

        if translation_segments:
            # 阶段1: 提取核心话题和营销问题
            topics, questions = self.extract_core_topics(
                podcast_name, guest_name, translation_segments
            )

            if topics:
                # 阶段2: 匹配时间戳
                topics_with_timestamps = self.match_timestamps(topics, translation_segments)

                # 阶段3: 时间戳换算（如果提供了播客音频信息）
                if podcast_audio_info and topics_with_timestamps:
                    topics_with_timestamps = self.convert_timestamps_for_podcast(
                        topics_with_timestamps,
                        original_video_duration_ms=podcast_audio_info.get('original_video_duration_ms', 0),
                        main_audio_duration_ms=podcast_audio_info.get('main_audio_duration_ms', 0),
                        prologue_duration_ms=podcast_audio_info.get('prologue_duration_ms', 0),
                        summary_duration_ms=podcast_audio_info.get('summary_duration_ms', 0),
                        music_intro_duration_ms=podcast_audio_info.get('music_intro_duration_ms', 5000),
                        music_transition_duration_ms=podcast_audio_info.get('music_transition_duration_ms', 3000)
                    )

            marketing_questions = questions

        # ========== 构建最终prompt ==========
        # 预构建"您将了解到"部分
        questions_section = ""
        if marketing_questions:
            questions_section = "\n".join([f"- {q}" for q in marketing_questions])

        # 预构建"时点内容"部分
        topics_section = ""
        has_timestamps = bool(topics_with_timestamps)
        if topics_with_timestamps:
            for t in topics_with_timestamps:
                topics_section += f"* {t['timestamp']} {t['title']}：{t['description']}\n"

        # 根据是否有预提取的时间戳，构建不同的prompt
        if has_timestamps:
            topics_instruction = f"""**预提取的时点内容**（必须原样使用，禁止修改时间戳）：
{topics_section}

**⚠️ 重要警告**：时点内容中的时间戳 [MM:SS] 是精确计算的，禁止修改、调整或编造新的时间戳。"""
        else:
            # 没有预提取的时间戳时，不要求AI生成时间戳
            topics_instruction = """**时点内容**：
由于无法获取准确的时间戳，请只生成话题标题和描述，不要添加时间戳。
格式：小标题：描述（60-100字，不要加粗）"""

        prompt = f"""
你是一位资深的播客运营专家，擅长撰写吸引人的播客节目介绍。

请根据以下信息，为播客节目生成一份专业的文案介绍：

**播客名称**：{podcast_name}
**嘉宾**：{guest_name}

**文字稿摘要**（前8000字符）：
{transcript[:8000]}

**预提取的营销问题**（直接使用，不要修改格式）：
{questions_section if questions_section else "（需要你生成3-4个引发好奇的问句）"}

{topics_instruction}

**要求**：

1. **开篇段落**（2句话，约80-100字）：
   - 用吸引人的方式引出核心亮点
   - 点出嘉宾的独特价值或核心观点

2. **故事/背景段落**（1段，约100-150字）：
   - 讲述嘉宾/公司的故事或背景
   - 突出最精彩的观点、案例或数据

3. **您将了解到：** 部分：
   - 直接使用上面预提取的营销问题
   - 格式：每行一个问句，以"-"开头
   - **不要加小标题，不要加时间戳**

4. **💡时点内容 | Key Topics** 部分：
   - **必须完全原样保留**上面预提取的时点内容
   - {"保持 * [MM:SS] 小标题：描述 的格式（不要加粗），禁止修改时间戳" if has_timestamps else "只使用 小标题：描述 的格式，不要添加时间戳"}
   - 每个描述保持60-100字的完整信息量
   - **严禁缩短、改写描述或编造新的时间戳**

5. **📺相关链接与资源**：
   - [视频来源]{video_url if video_url else 'www.youtube.com'}

6. **结尾免责声明**（固定格式）：
   本播客采用虚拟主持人进行播客翻译的音频制作，因此有可能会有一些地方听起来比较奇怪。如想了解更多信息，请关注微信公众号"西经东译"获取AI最新资讯。

**关键要求**：
- "您将了解到"部分：只有问句列表，无小标题，无时间戳
- "时点内容"部分：{"有时间戳（必须使用预提取的，禁止编造）" if has_timestamps else "无时间戳"}，格式为 * [时间戳] 小标题：描述（不要加粗）
- **严禁编造或修改时间戳**
- 总长度控制在 800-1200 字之间

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
                "maxOutputTokens": 8192,
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
        video_url: Optional[str] = None,
        podcast_audio_info: Optional[Dict] = None
    ) -> Optional[str]:
        """
        从文件生成播客介绍文案（一站式方法，v2.6时间戳换算）

        Args:
            start_prompt_file: start_prompt.md文件路径
            asr_file: ASR结果文件路径
            video_url: 原视频URL（可选）
            podcast_audio_info: 播客音频信息（可选），用于时间戳换算
                {
                    'original_video_duration_ms': 原视频时长（毫秒）,
                    'main_audio_duration_ms': 主音频时长（毫秒）,
                    'prologue_duration_ms': 开场白时长（毫秒）,
                    'summary_duration_ms': 概要时长（毫秒）,
                    'music_intro_duration_ms': 片头音乐时长（毫秒）,
                    'music_transition_duration_ms': 过渡音乐时长（毫秒）
                }

        Returns:
            生成的文案，或None
        """
        # 解析播客信息
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

        # 加载翻译段落（用于两阶段提取）
        translation_segments = self.load_translation_segments(asr_file)

        # 生成文案（使用两阶段提取）
        description = self.generate_description(
            podcast_name=podcast_name,
            guest_name=guest_name,
            transcript=transcript,
            video_url=video_url,
            translation_segments=translation_segments,
            podcast_audio_info=podcast_audio_info
        )

        return description

    def generate_wx_description(
        self,
        podcast_name: str,
        guest_name: str,
        transcript: str,
        video_url: Optional[str] = None
    ) -> Optional[str]:
        """
        生成公众号深度文案

        Args:
            podcast_name: 播客名称
            guest_name: 嘉宾名称
            transcript: ASR文字稿
            video_url: 原视频URL（可选）

        Returns:
            生成的公众号文案（Markdown格式），或None
        """
        print(f"\n{'='*80}")
        print(f"生成公众号深度文案")
        print(f"{'='*80}")
        print(f"播客: {podcast_name}")
        print(f"嘉宾: {guest_name}\n")

        prompt = f"""
你是一位资深的公众号内容运营专家，擅长撰写深度解读文章。

请根据以下播客访谈内容，生成一篇适合公众号发布的深度文章。

**播客名称**：{podcast_name}
**嘉宾**：{guest_name}

**访谈文字稿**（前20000字符）：
{transcript[:20000]}

**文章结构要求**：

## 一、备选标题（3个）
提供3个不同风格的爆款标题：
1. [数据型] 包含具体数字的标题
2. [悬念型] 引发好奇的标题
3. [金句型] 包含嘉宾金句的标题

---

## 二、开篇引入（约200字）
- 用一个引人入胜的场景、问题或金句开篇
- 可以是反常识的观点、惊人的数据、或嘉宾金句
- 简要介绍本期访谈的核心主题和价值

---

## 三、嘉宾/公司背景（约300字）
深度介绍嘉宾和公司背景：
- 嘉宾的职业经历和成就
- 公司的发展历程和里程碑
- 在行业中的地位和影响力
- 为什么这个人/公司值得关注

---

## 四、核心观点深度解读（约800-1000字）
从访谈中提取 **4-5个核心观点**，每个观点包含：
- **观点标题**（一句话总结，加粗）
- **观点详解**（2-3段，展开说明背景、原因、方法）
- **案例/数据支撑**（具体例子或数字）

格式示例：
### 观点1：[标题]
[详细展开2-3段...]

### 观点2：[标题]
[详细展开2-3段...]

---

## 五、金句集锦（5-8句）
从访谈中提取最有力量、最有洞见的金句，用引用格式：
> "金句内容..."

---

## 六、关键数据一览
用表格汇总访谈中提到的关键数据：
| 指标 | 数据 | 说明 |
|------|------|------|

---

## 七、延伸思考（约300字）
基于访谈内容，提供更宏观的行业视角：
- 这个观点对行业意味着什么？
- 对从业者/读者有什么启发？
- 2-3个关键启示点

---

## 八、结尾
- 收听完整访谈的引导（播客链接：{video_url if video_url else 'www.youtube.com'}）
- 互动引导（引导读者评论）
- 关注引导（关注「西经东译」）

**关键要求**：
1. 总字数 **2000-2500字**
2. 必须提取 **5-8个具体数字**
3. 必须提取 **5-8句金句**
4. 核心观点要 **深度展开**，不能只是一句话概括
5. 语言风格：专业但不枯燥，有深度但易读
6. 使用 Markdown 格式，适合公众号编辑器

请直接输出完整文章，不要输出思考过程。
"""

        # 使用Gemini Pro模型
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
                "maxOutputTokens": 8192,
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

                print("正在调用Gemini API生成公众号文案...")

                response = requests.post(
                    url,
                    json=payload,
                    proxies=self.proxies,
                    timeout=120
                )

                if response.status_code == 200:
                    result = response.json()

                    if 'candidates' in result and len(result['candidates']) > 0:
                        candidate = result['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            wx_description = candidate['content']['parts'][0].get('text', '').strip()

                            print(f"\n✓ 公众号文案生成成功")
                            print(f"✓ 字数: {len(wx_description)} 字")

                            return wx_description

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

    def generate_wx_from_files(
        self,
        start_prompt_file: Path,
        asr_file: Path,
        video_url: Optional[str] = None,
        output_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """
        从文件生成公众号文案并保存

        Args:
            start_prompt_file: start_prompt.md文件路径
            asr_file: ASR结果文件路径
            video_url: 原视频URL（可选）
            output_dir: 输出目录（默认: wx_description/）

        Returns:
            生成的文件路径，或None
        """
        import re

        # 解析播客信息
        with open(start_prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()

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

        # 生成公众号文案
        wx_description = self.generate_wx_description(
            podcast_name=podcast_name,
            guest_name=guest_name,
            transcript=transcript,
            video_url=video_url
        )

        if not wx_description:
            return None

        # 保存到文件
        if output_dir is None:
            output_dir = Path("wx_description")
        output_dir.mkdir(parents=True, exist_ok=True)

        # 清理文件名中的非法字符
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', podcast_name)
        output_file = output_dir / f"{safe_name}.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(wx_description)

        print(f"\n✓ 公众号文案已保存到: {output_file}")

        return output_file

