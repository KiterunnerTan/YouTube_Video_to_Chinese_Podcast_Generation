"""
测试 MiniMax 预设音色的稳定性
用不同情绪的文本测试同一个音色，观察音色变化幅度
"""
import os
import sys
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 测试的预设音色列表
# 参考: https://platform.minimaxi.com/document/VoiceList
TEST_VOICES = [
    # 男声 - 播音/专业类
    ("male-qn-jingying", "精英男声 - 适合商业访谈"),
    ("presenter_male", "播音男声 - 正式专业"),
    ("audiobook_male_1", "有声书男声1"),
    ("audiobook_male_2", "有声书男声2"),
    # 女声 - 播音/专业类
    ("female-shaonv", "少女音 - 年轻活泼"),
    ("female-yujie", "御姐音 - 成熟知性"),
    ("presenter_female", "播音女声 - 正式专业"),
    ("audiobook_female_1", "有声书女声1"),
]

# 测试文本 - 不同情绪
TEST_TEXTS = {
    "neutral": "这个项目的核心理念是，让每个人都能拥有一个超级强大的AI助手，它可以帮你处理日常生活中的各种事务。",
    "excited": "哇！这太神奇了！我简直不敢相信它竟然能自动修复bug，然后还在推特上回复说问题已经解决了！",
    "serious": "但是我们必须认真思考一个问题：当AI可以访问你电脑上的所有数据时，安全性和隐私保护该如何保障？",
    "casual": "嗯，其实也没那么复杂啦。你只要把它连上WhatsApp，然后跟它说话就行了，就像和朋友聊天一样。",
}


def generate_test_audio(voice_id: str, text: str, output_path: Path, api_key: str, group_id: str) -> bool:
    """生成测试音频"""
    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={group_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
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

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            result = response.json()

            if "data" in result and "audio" in result["data"]:
                audio_hex = result["data"]["audio"]
                audio_bytes = bytes.fromhex(audio_hex)

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)

                return True
            else:
                print(f"  ❌ No audio data in response")
                return False
        else:
            print(f"  ❌ API error: {response.status_code} - {response.text[:200]}")
            return False

    except Exception as e:
        print(f"  ❌ Exception: {str(e)}")
        return False


def main():
    api_key = os.getenv("MINIMAX_API_KEY")
    group_id = os.getenv("MINIMAX_GROUP_ID")

    if not api_key or not group_id:
        print("❌ 请在 .env 中配置 MINIMAX_API_KEY 和 MINIMAX_GROUP_ID")
        sys.exit(1)

    output_dir = Path("output/voice_stability_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("MiniMax 预设音色稳定性测试")
    print("=" * 60)
    print(f"\n测试音色数量: {len(TEST_VOICES)}")
    print(f"测试情绪数量: {len(TEST_TEXTS)}")
    print(f"总共生成音频: {len(TEST_VOICES) * len(TEST_TEXTS)} 个")
    print(f"\n输出目录: {output_dir.absolute()}")
    print("-" * 60)

    results = {}

    for voice_id, voice_desc in TEST_VOICES:
        print(f"\n📢 测试音色: {voice_id} ({voice_desc})")
        voice_dir = output_dir / voice_id
        results[voice_id] = {"desc": voice_desc, "files": []}

        for emotion, text in TEST_TEXTS.items():
            output_file = voice_dir / f"{emotion}.mp3"
            print(f"  ├─ {emotion}: ", end="", flush=True)

            success = generate_test_audio(voice_id, text, output_file, api_key, group_id)

            if success:
                print(f"✓ {output_file.name}")
                results[voice_id]["files"].append(str(output_file))
            else:
                print(f"✗ 失败")

            # 避免API限流
            time.sleep(0.5)

    # 打印结果摘要
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print(f"\n请到以下目录收听测试音频，对比同一音色在不同情绪下的表现:")
    print(f"  {output_dir.absolute()}")
    print("\n每个音色文件夹下有 4 个文件:")
    print("  - neutral.mp3  (中性陈述)")
    print("  - excited.mp3  (兴奋激动)")
    print("  - serious.mp3  (严肃认真)")
    print("  - casual.mp3   (轻松随意)")
    print("\n评估标准:")
    print("  ✓ 好的音色: 情绪有变化，但音色本身(音质/共鸣)保持稳定")
    print("  ✗ 差的音色: 不同情绪下听起来像换了个人")

    # 保存结果索引
    import json
    with open(output_dir / "test_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n结果索引已保存: {output_dir / 'test_results.json'}")


if __name__ == "__main__":
    main()
