"""
测试TTS分段大小上限 - 找到当前环境的稳定上限

测试策略:
- 从5000字符开始,逐档降低到1000字符
- 找到第一个成功的档位后,验证2次稳定性
- 早停策略:避免浪费API额度
"""
import json
import time
from pathlib import Path
from config import Config
from utils.tts_generator_v1_4 import GeminiTTSGeneratorV14, VoiceManager


def main():
    Config.validate()
    Config.setup_proxy()

    # 读取翻译结果,获取真实中文文本
    translation_file = Path("output/translations/gemini_3_translations_v1_4_fixed.json")
    with open(translation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        translations = data["translations"]

    # 合并所有翻译文本
    full_text = ""
    for trans in translations:
        full_text += trans['translated_text'] + "\n"

    print(f"\n{'='*60}")
    print(f"TTS分段大小上限测试")
    print(f"{'='*60}")
    print(f"测试文本总字符数: {len(full_text)}")
    print(f"测试数据源: {translation_file}")
    print(f"代理: 7890端口")
    print(f"模型: gemini-2.5-pro-preview-tts")
    print(f"{'='*60}\n")

    # 测试档位(从高到低)
    test_sizes = [5000, 4000, 3000, 2500, 2000, 1500, 1000]

    # 创建TTS生成器
    voice_manager = VoiceManager()
    tts_generator = GeminiTTSGeneratorV14(
        api_key=Config.GEMINI_API_KEY,
        model_name="gemini-2.5-pro-preview-tts",
        voice_manager=voice_manager,
        enable_cache=True
    )

    # 创建临时输出目录
    test_output_dir = Path("output/test_segment_limits")
    test_output_dir.mkdir(parents=True, exist_ok=True)

    # 测试结果
    results = []
    stable_limit = None

    for size in test_sizes:
        print(f"\n{'='*60}")
        print(f"测试 {size} 字符...")
        print(f"{'='*60}")

        # 提取测试文本
        test_text = full_text[:size]
        actual_chars = len(test_text)
        print(f"实际字符数: {actual_chars}")

        # 尝试生成
        success = False
        error_msg = None

        try:
            output_path = test_output_dir / f"test_{size}chars.mp3"
            tts_generator.generate_audio(text=test_text, output_path=output_path)

            print(f"  ✓ 成功!")
            success = True

            # 如果成功,进行2次验证
            print(f"\n验证稳定性...")
            verification_count = 2
            all_verified = True

            for i in range(verification_count):
                print(f"  验证 {i+1}/{verification_count}...", end=" ")
                try:
                    verify_output = test_output_dir / f"test_{size}chars_verify{i+1}.mp3"
                    tts_generator.generate_audio(text=test_text, output_path=verify_output)
                    print(f"✓ 成功")
                    time.sleep(3)  # 延迟3秒
                except Exception as e:
                    print(f"✗ 失败: {str(e)}")
                    all_verified = False
                    break

            if all_verified:
                stable_limit = size
                print(f"\n🎉 找到稳定上限: {size} 字符")
                results.append({
                    "size": size,
                    "status": "stable",
                    "verified": True
                })
                break  # 早停
            else:
                results.append({
                    "size": size,
                    "status": "unstable",
                    "verified": False,
                    "error": "验证失败"
                })

        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ 失败: {error_msg}")
            results.append({
                "size": size,
                "status": "failed",
                "error": error_msg
            })

        # 延迟5秒避免速率限制
        if not stable_limit:
            time.sleep(5)

    # 输出最终结果
    print(f"\n{'='*60}")
    print(f"测试完成")
    print(f"{'='*60}")

    if stable_limit:
        print(f"\n✅ 稳定上限: {stable_limit} 字符")
        print(f"\n建议:")
        if stable_limit > 950:
            print(f"  - 可以将分段大小从950提升到{stable_limit}")
            print(f"  - 预计可减少 {int((1 - 950/stable_limit) * 100)}% 的segment数量")
        else:
            print(f"  - 保持当前950字符配置")
            print(f"  - 历史数据准确,无需调整")
    else:
        print(f"\n❌ 所有档位均失败")
        print(f"  - 建议保持当前950字符配置")
        print(f"  - 或检查网络/代理问题")

    # 保存测试报告
    report_file = test_output_dir / "test_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "proxy_port": "7890",
            "model": "gemini-2.5-pro-preview-tts",
            "test_sizes": test_sizes,
            "stable_limit": stable_limit,
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n测试报告已保存: {report_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
