# 代理配置指南 (Proxy Setup Guide)

由于 Google 服务在中国大陆无法直接访问，您需要配置代理才能使用 Gemini API 进行翻译和 TTS。

## 📋 前置条件

确保您已经有可用的代理工具，例如：
- **Clash for Windows** / **ClashX** (推荐)
- **V2Ray** / **V2RayN**
- **Shadowsocks**
- **其他 VPN/代理工具**

## 🔧 配置步骤

### 步骤 1: 启动代理工具

1. 打开您的代理工具（如 Clash、V2Ray 等）
2. 确保代理已连接并正常运行
3. 查看代理的**本地监听端口**

**常见代理端口：**
- Clash: `7890` (HTTP/HTTPS) 或 `7891` (SOCKS5)
- V2Ray: `10809` (HTTP) 或 `10808` (SOCKS5)
- Shadowsocks: `1080` (SOCKS5)

### 步骤 2: 编辑 .env 文件

打开项目根目录的 `.env` 文件，找到代理配置部分：

```env
# 代理设置 (在中国大陆访问 Google 服务时需要)
# 取消注释并配置您的代理地址
# HTTP_PROXY=http://127.0.0.1:7890
# HTTPS_PROXY=http://127.0.0.1:7890
# 或者使用 SOCKS5 代理
# ALL_PROXY=socks5://127.0.0.1:7890
```

**取消注释并根据您的代理工具配置：**

#### 选项 A: HTTP/HTTPS 代理（推荐）

```env
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

将 `7890` 替换为您的代理工具的 HTTP 端口。

#### 选项 B: SOCKS5 代理

```env
ALL_PROXY=socks5://127.0.0.1:7891
```

将 `7891` 替换为您的代理工具的 SOCKS5 端口。

### 步骤 3: 测试代理连接

运行以下命令测试代理是否正常工作：

```bash
# 激活虚拟环境
source venv/bin/activate

# 尝试翻译之前处理好的 ASR 结果
python main.py translate output/asr_results/processed_20251214_164520.json
```

**预期输出：**
```
✓ HTTP_PROXY set: http://127.0.0.1:7890
✓ HTTPS_PROXY set: http://127.0.0.1:7890
Translating 1 segments...
Translating segment 0...
Segment 0 translated successfully
...
```

如果看到 `✓ HTTP_PROXY set` 消息，说明代理已正确配置。

## 🎯 完整流程测试

代理配置成功后，可以重新运行完整流程：

```bash
source venv/bin/activate

# 使用之前下载的视频
python main.py full-pipeline "output/downloads/AI bubble？ Nvidia CEO says 3 things are happening.mp4" -o final_podcast.mp3
```

流程将按顺序执行：
1. ✅ ASR 识别（已成功）
2. ✅ 文本处理（已成功）
3. 🔄 翻译（通过代理访问 Gemini）
4. 🔄 TTS 生成（通过代理访问 Gemini）
5. 🔄 音频合并

## ❗ 常见问题

### 1. 代理连接超时

**错误信息：**
```
503 failed to connect to all addresses
Operation timed out
```

**解决方案：**
- 确认代理工具已启动并正常运行
- 检查 `.env` 中配置的端口是否正确
- 尝试在浏览器中访问 Google 测试代理是否正常

### 2. 端口被占用

**错误信息：**
```
Connection refused
```

**解决方案：**
- 检查代理工具是否正在运行
- 确认代理端口号是否正确
- 尝试重启代理工具

### 3. 代理不生效

**检查步骤：**
```bash
# 在终端中手动测试
export HTTPS_PROXY=http://127.0.0.1:7890
curl -I https://www.google.com
```

如果返回 200 OK，说明代理正常。

### 4. SOCKS5 代理不工作

如果使用 SOCKS5 代理遇到问题，尝试切换到 HTTP 代理：
```env
# 改用 HTTP 代理
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
# ALL_PROXY=socks5://127.0.0.1:7891  # 注释掉 SOCKS5
```

## 📊 不同代理工具的配置示例

### Clash for Windows / ClashX

```env
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

或使用 SOCKS5：
```env
ALL_PROXY=socks5://127.0.0.1:7891
```

### V2Ray / V2RayN

```env
HTTP_PROXY=http://127.0.0.1:10809
HTTPS_PROXY=http://127.0.0.1:10809
```

或使用 SOCKS5：
```env
ALL_PROXY=socks5://127.0.0.1:10808
```

### Shadowsocks

```env
ALL_PROXY=socks5://127.0.0.1:1080
```

## 🔒 安全提示

1. **不要将包含代理配置的 .env 文件提交到 Git**
   - `.env` 文件已在 `.gitignore` 中

2. **仅在本地使用**
   - 代理配置仅在本地开发环境使用
   - 部署到服务器时根据实际网络环境调整

3. **选择可信的代理服务**
   - API Key 等敏感信息会通过代理传输
   - 使用可信的代理服务提供商

## 📚 进一步帮助

如果仍然遇到问题：
1. 检查代理工具的日志
2. 尝试在浏览器中访问 https://gemini.google.com 测试连通性
3. 确认您的代理支持 HTTPS 流量
4. 尝试使用不同的代理节点

## ✅ 验证清单

配置完成后，请确认：
- [ ] 代理工具已启动并正常运行
- [ ] `.env` 文件中的代理配置已取消注释
- [ ] 代理端口号与工具设置一致
- [ ] 运行 CLI 命令时看到 `✓ HTTP_PROXY set` 消息
- [ ] 可以成功访问 Google 服务

配置成功后，您就可以正常使用完整的 YouTube 视频转播客流程了！🎉
