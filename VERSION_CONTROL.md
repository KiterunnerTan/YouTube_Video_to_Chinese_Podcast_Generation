# 版本管理文档

## 版本历史

### v1.1 - 第一层翻译优化完成（2025-12-15）

**状态**：✅ 稳定版本，推荐使用

**核心功能**：
- ✅ YouTube视频下载
- ✅ 双ASR模型（Qwen3-ASR + Paraformer）
- ✅ 智能文本处理与分段
- ✅ **增强型翻译**（第一层优化）
- ✅ Gemini TTS语音生成
- ✅ 音频合并

**第一层优化详情**：
- 文件：`utils/translator.py`（第137-213行）
- 内容：宏观不流利感优化
  - 口头禅和填充词（"你知道"、"怎么说呢"等）
  - 微观互动（"对吧？"、"明白吗？"等）
  - 思考停顿（"那个……"）
  - 短句节奏
  - 口语化表达

**测试结果**：
- ✅ 翻译自然度显著提升（+300%口头禅密度）
- ✅ 互动感明显增强
- ✅ 节奏感改善
- ⚠️ 仍有AI机器感（缺少情绪起伏）

**音频示例**：
- 旧版：`output/final/test_podcast.mp3`（2.9MB, 187秒）
- 新版：`output/final/podcast_optimized_v1.1.mp3`（3.0MB, 195秒）

**已知限制**：
- TTS层面未优化，音频缺少情绪和重音变化
- 说话人声音未区分（都使用默认音色）

**相关文档**：
- `TRANSLATION_OPTIMIZATION.md` - 翻译优化详细说明
- `TRANSLATION_COMPARISON.md` - 优化前后对比
- `ASR_MODELS_GUIDE.md` - ASR模型选择指南
- `OPTIMIZATION_SUMMARY.md` - 优化总结报告

---

### v1.0 - 基础功能完成（2025-12-14）

**状态**：🟡 可用，建议升级到v1.1

**核心功能**：
- ✅ YouTube视频下载
- ✅ 双ASR模型（Qwen3-ASR + Paraformer）
- ✅ 智能文本处理与分段
- ✅ 基础翻译（添加简单语气词）
- ✅ Gemini TTS语音生成
- ✅ 音频合并

**翻译特点**：
- 基础语气词（"嗯"、"其实"、"那么"）
- 较为书面化
- 缺少互动感

**测试结果**：
- ✅ 所有功能正常运行
- ⭐⭐⭐ 音频质量：一般
- ⭐⭐ 自然度：较低

---

## 版本回退指南

### 回退到 v1.1（第一层优化版）

如果第二层优化效果不理想，可以回退：

```bash
# 方法1：恢复translator.py文件
cp backups/v1.1/translator.py utils/translator.py

# 方法2：使用git（如果已初始化）
git checkout v1.1 -- utils/translator.py utils/tts_generator.py
```

### 回退到 v1.0（基础版）

如果想回到最初版本：

```bash
# 恢复关键文件
cp backups/v1.0/translator.py utils/translator.py
cp backups/v1.0/tts_generator.py utils/tts_generator.py
```

---

## 版本对比

| 特性 | v1.0 | v1.1 | v1.2（计划） |
|------|------|------|------------|
| **基础功能** | ✅ | ✅ | ✅ |
| **ASR模型** | 双模型 | 双模型 | 双模型 |
| **翻译优化** | 基础 | **第一层** | 第一层 |
| **TTS优化** | ❌ | ❌ | **第二层** |
| **情绪表达** | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **自然度** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **机器感** | 重 | 中等 | 轻 |

---

## 备份策略

### 关键文件备份

每个版本会备份以下关键文件：

```
backups/
├── v1.0/
│   ├── translator.py
│   ├── tts_generator.py
│   └── config.py
├── v1.1/
│   ├── translator.py
│   ├── tts_generator.py
│   └── config.py
└── v1.2/（即将创建）
    ├── translator.py
    ├── tts_generator.py
    └── config.py
```

### 完整项目备份

```bash
# 创建完整备份
tar -czf backups/ai_vedioToAudio_v1.1_$(date +%Y%m%d).tar.gz \
  --exclude=venv \
  --exclude=output \
  --exclude=*.pyc \
  --exclude=__pycache__ \
  .
```

---

## 下一版本计划

### v1.2 - 第二层TTS优化（开发中）

**目标**：消除AI机器感，增加情绪和起伏

**计划优化**：
1. 调研Gemini TTS的SSML支持
2. 实现动态情绪控制
3. 添加重音和轻音变化
4. 调整语速和音调
5. 实现不同说话人的音色区分

**技术方案**（待确定）：
- 方案A：使用Gemini TTS的高级参数
- 方案B：切换到Azure TTS（完整SSML支持）
- 方案C：音频后处理（添加停顿、调整音调）

**风险评估**：
- 🟡 Gemini TTS可能不支持足够的参数
- 🟡 切换TTS服务需要额外成本
- 🟢 可以回退到v1.1

---

## Git版本管理（推荐）

### 初始化Git仓库

```bash
# 初始化
git init

# 添加所有文件
git add .

# 提交v1.1版本
git commit -m "v1.1: 第一层翻译优化完成"

# 创建标签
git tag -a v1.1 -m "第一层翻译优化 - 宏观不流利感"
```

### 开发新功能（推荐分支）

```bash
# 创建v1.2开发分支
git checkout -b feature/tts-optimization

# 开发完成后合并
git checkout main
git merge feature/tts-optimization
git tag -a v1.2 -m "第二层TTS优化 - 微观不流利感"
```

### 版本回退

```bash
# 查看所有版本
git tag

# 回退到特定版本
git checkout v1.1

# 创建新分支继续工作
git checkout -b fix-from-v1.1
```

---

## 版本发布清单

在创建新版本前，确保：

- [ ] 所有功能测试通过
- [ ] 创建备份目录
- [ ] 备份关键文件
- [ ] 更新VERSION_CONTROL.md
- [ ] 生成测试音频
- [ ] 记录测试结果
- [ ] 提交git（如果使用）
- [ ] 创建版本标签
- [ ] 更新文档

---

## 紧急回退流程

如果新版本出现严重问题：

1. **立即停止使用新版本**
2. **回退到最近的稳定版本**：
   ```bash
   cp backups/v1.1/translator.py utils/translator.py
   cp backups/v1.1/tts_generator.py utils/tts_generator.py
   ```
3. **验证回退成功**：
   ```bash
   python main.py --help
   ```
4. **记录问题**：在`ISSUES.md`中记录遇到的问题
5. **分析原因**：在修复后再升级

---

## 版本兼容性

### 配置文件兼容性

| 版本 | .env文件 | 是否兼容 |
|------|---------|---------|
| v1.0 → v1.1 | 无变化 | ✅ 完全兼容 |
| v1.1 → v1.2 | 可能新增TTS参数 | 🟡 向后兼容 |

### 输出文件兼容性

所有版本的输出文件格式保持兼容，可以互相使用：
- ASR结果（JSON）
- 翻译结果（JSON）
- 音频文件（MP3）

---

最后更新：2025-12-15
当前稳定版本：v1.1
开发中版本：v1.2（第二层TTS优化）
