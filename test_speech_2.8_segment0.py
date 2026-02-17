"""
测试 speech-2.8-hd 模型的音调一致性
使用 segment_0 的完整翻译内容进行测试
"""
import json
import time
import requests
import subprocess
import tempfile
from pathlib import Path
from config import Config

# segment_0 的翻译内容
SEGMENT_0_TEXT = """speaker_1: 你的新年决心，很可能最后会以失败告终。但这没关系，大多数人都是如此。有研究表明，大概有80%到90%的人，最终都会放弃他们的新年决心。这背后的根本原因在于……大多数人并不是真的想从内心深处做出改变。
speaker_0: 百分之八九十！哇，这个比例真的高得吓人。那为什么大家改变自己生活的方式，从一开始就完全错了呢？
speaker_1: 因为当人们想要改变生活时，他们会去制定新年决心，仅仅因为……其他人都在这么做。人性很有意思的一点是，我们渴望获得他人认可的程度，远远超过了取悦自己。我们通过各种社会地位的游戏来创造一种非常肤浅的意义感，但这根本满足不了真正改变所需要的深层条件，也就是让你说服自己今年要变得更自律、更高效。
speaker_0: 这倒是实话，很多时候确实是为了朋友圈或者给别人看。
speaker_1: 对。你看，我不是在居高临下地评判大家。说实话，我自己放弃过的目标，可能比我设定过的还要多十倍。很多人可能也注意到了，比如我之前说要写的那本书……我现在已经不写了。但我反而觉得，对大多数人来说，这才是常态。你应该放弃比设立更多的目标，不然你怎么能筛选出那个真正正确的目标呢？不过，人们总是尝试改变生活，却几乎每次都彻底失败，这个问题依然存在。严重到什么程度呢？就是每年一月份健身房都人满为患，到了二月份就空空如也，这甚至都成了一个段子。
speaker_0: 确实是这样。虽然说新年决心这个形式可能有点傻，但反思生活、做出改变的愿望本身是没错的。
speaker_1: 是的。而且人性就是这么折磨人。最糟糕的感觉就是，你对自己许下承诺，然后又亲手打破它，尤其当这个过程一再重复时，你会开始感到无助。如果你不知道自己在做什么，这个循环可能会持续好几年，你总是渴望改变，却永远无法实现。所以，无论你是想创业，想彻底改变自己的身材，还是想冒一次险去追求有意义的生活，并且不想在两周后就放弃……今天我就想分享七个，可能是我有史以来分享过的、最具冲击力的观点。这些观点你以前可能从未听过，它们关乎行为改变、心理学和个人效率，能帮助你在新的一年里真正做到这些。
speaker_0: 听起来这正是大家需要的。
speaker_1: 我想强调一下，这次分享会非常系统和深入。它不是那种你看完就忘的视频。我希望你能认真对待它，把它收藏起来，做笔记，并且需要你专门留出时间去思考。我们会先讨论六个核心理念，然后第七个，与其说是理念，不如说是一个完整的实践方案。我们会一起深入挖掘你的内心。如果你能认真对待，整个过程可能会让你情绪非常激动，并且……需要花费整整一天的时间来完成。"""

# 音色配置
VOICE_MAPPING = {
    "speaker_0": "Inspirational_girl",
    "speaker_1": "Deep_Voice_Man"
}

def parse_segments(text):
    """解析文本为 segments"""
    import re
    segments = []
    pattern = r'^(speaker_\d+):\s*(.+)$'

    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        match = re.match(pattern, line)
        if match:
            speaker, content = match.groups()
            voice_id = VOICE_MAPPING.get(speaker, "Deep_Voice_Man")
            segments.append({
                "speaker": speaker,
                "content": content.strip(),
                "voice_id": voice_id
            })
    return segments

def generate_audio_segment(text, voice_id, output_path):
    """调用 MiniMax API 生成单个音频段"""
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={Config.MINIMAX_GROUP_ID}"
    headers = {
        "Authorization": f"Bearer {Config.MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "speech-2.8-hd",
        "text": text,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": 1.0
        },
        "audio_setting": {
            "format": "mp3",
            "sample_rate": 24000
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=90)

    if response.status_code != 200:
        raise RuntimeError(f"API error: {response.status_code} - {response.text}")

    result = response.json()
    if "data" not in result or "audio" not in result["data"]:
        raise RuntimeError(f"No audio data: {result}")

    audio_bytes = bytes.fromhex(result["data"]["audio"])
    with open(output_path, 'wb') as f:
        f.write(audio_bytes)

    return output_path

def merge_audio_files(audio_files, output_path):
    """用 ffmpeg 合并音频文件"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        for audio_file in audio_files:
            f.write(f"file '{Path(audio_file).absolute()}'\n")
        concat_list = f.name

    cmd = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_list,
        '-c', 'copy',
        '-y',
        str(Path(output_path).absolute())
    ]

    subprocess.run(cmd, capture_output=True, check=True)
    Path(concat_list).unlink()

def main():
    print("=" * 60)
    print("测试 speech-2.8-hd 模型音调一致性")
    print("=" * 60)

    # 解析 segments
    segments = parse_segments(SEGMENT_0_TEXT)
    print(f"\n共 {len(segments)} 个 segments:")
    for i, seg in enumerate(segments):
        print(f"  {i+1}. {seg['speaker']} -> {seg['voice_id']}: {seg['content'][:30]}...")

    # 创建临时目录
    temp_dir = Path("output/test_speech_2.8")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 生成每个 segment 的音频
    audio_files = []
    print(f"\n开始生成音频...")

    for i, segment in enumerate(segments):
        output_file = temp_dir / f"segment_{i:04d}.mp3"
        print(f"  生成 {i+1}/{len(segments)}: {segment['speaker']} ({segment['voice_id']})")

        try:
            generate_audio_segment(segment["content"], segment["voice_id"], output_file)
            audio_files.append(output_file)
            print(f"    ✓ 完成")
        except Exception as e:
            print(f"    ✗ 失败: {e}")
            return

        # 等待 3 秒避免 RPM 限制
        if i < len(segments) - 1:
            print(f"    等待 3 秒...")
            time.sleep(3)

    # 合并音频
    output_path = Path("output/test_speech_2.8_segment0.mp3")
    print(f"\n合并音频...")
    merge_audio_files(audio_files, output_path)

    print(f"\n✓ 测试完成!")
    print(f"✓ 输出文件: {output_path}")
    print(f"\n请听一下这个文件，对比原来的效果，看音调一致性是否有改善。")

if __name__ == "__main__":
    main()
