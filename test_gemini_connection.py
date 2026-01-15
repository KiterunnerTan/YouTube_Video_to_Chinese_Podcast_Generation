#!/usr/bin/env python3
"""测试 Gemini API 连接"""
import os
import requests
from config import Config

# 设置代理
Config.setup_proxy()

# 测试 API 连接
api_key = Config.GEMINI_API_KEY
base_url = "https://generativelanguage.googleapis.com/v1beta"

# 构建代理字典
proxies = {}
if os.getenv('HTTP_PROXY'):
    proxies['http'] = os.getenv('HTTP_PROXY')
if os.getenv('HTTPS_PROXY'):
    proxies['https'] = os.getenv('HTTPS_PROXY')

print("=" * 80)
print("🧪 测试 Gemini API 连接")
print("=" * 80)
print(f"API Key: {api_key[:20]}..." if api_key else "❌ 未设置 API Key")
print(f"代理设置: {proxies}")
print()

# 测试简单的 API 调用
test_url = f"{base_url}/models/gemini-2.0-flash-exp:generateContent"

payload = {
    "contents": [{
        "parts": [{
            "text": "Say hello in Chinese."
        }]
    }]
}

params = {'key': api_key}

print("正在发送测试请求...")
try:
    response = requests.post(
        test_url,
        json=payload,
        params=params,
        proxies=proxies,
        timeout=30
    )

    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        print("✅ Gemini API 连接成功！")
        result = response.json()
        if 'candidates' in result and len(result['candidates']) > 0:
            text = result['candidates'][0]['content']['parts'][0]['text']
            print(f"响应内容: {text}")
    else:
        print(f"❌ API 调用失败")
        print(f"错误信息: {response.text}")

except Exception as e:
    print(f"❌ 连接失败: {e}")

print("=" * 80)
