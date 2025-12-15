# ASR模型选择指南

## 为什么有两个ASR模型？

本项目提供两个ASR模型供选择，各有优势和适用场景。

## 模型对比

### 1. Qwen3-ASR-Flash（快速模式）

**特点**：
- ✅ **快速高效**：处理速度更快
- ✅ **配置简单**：只需DashScope API Key，无需OSS配置
- ✅ **成本较低**：无需额外的OSS存储成本
- ✅ **适合新手**：使用门槛低，配置简单

**限制**：
- ❌ **不支持说话人分离**：无法区分不同说话人
- ❌ **单人场景**：适合单人讲解、演讲等内容

**适用场景**：
- 单人演讲视频
- 教学视频
- 个人Vlog
- TED演讲
- 快速测试和原型开发

**配置要求**：
```env
DASHSCOPE_API_KEY=your_api_key
```

**使用方法**：
```bash
# 分步执行
python main.py asr video.mp4 -l zh -l en -o asr_result.json

# 完整pipeline（不使用说话人分离）
python main.py full-pipeline video.mp4 -o podcast.mp3 --no-diarization
```

---

### 2. Paraformer（说话人分离模式）

**特点**：
- ✅ **说话人分离**：自动识别和标记不同说话人
- ✅ **多人对话**：适合访谈、对话、讨论节目
- ✅ **更自然**：保留对话的互动感和节奏
- ✅ **高质量**：ASR准确度高

**限制**：
- ❌ **需要OSS配置**：必须配置阿里云OSS存储
- ❌ **配置复杂**：需要创建Bucket和配置AccessKey
- ❌ **有额外成本**：OSS存储和流量费用
- ❌ **处理较慢**：需要先上传文件到OSS

**适用场景**：
- 播客访谈
- 多人讨论
- 圆桌会议
- 对话节目
- 需要区分说话人的任何内容

**配置要求**：
```env
DASHSCOPE_API_KEY=your_api_key
OSS_ACCESS_KEY_ID=your_oss_key_id
OSS_ACCESS_KEY_SECRET=your_oss_key_secret
OSS_BUCKET_NAME=your_bucket_name
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

**OSS配置步骤**：
1. 访问 [阿里云OSS控制台](https://oss.console.aliyun.com/)
2. 创建Bucket（建议使用标准存储、私有读写）
3. 访问 [RAM控制台](https://ram.console.aliyun.com/manage/ak) 创建AccessKey
4. 配置到 `.env` 文件

**使用方法**：
```bash
# 完整pipeline（默认使用说话人分离）
python main.py full-pipeline video.mp4 -o podcast.mp3

# 指定说话人数量（可选，不指定则自动检测）
python main.py full-pipeline video.mp4 -o podcast.mp3 -s 2
```

---

## 快速选择指南

### 选择Qwen3-ASR-Flash（快速模式），如果：
- ✅ 视频只有一个人说话
- ✅ 想快速测试功能
- ✅ 不想配置OSS
- ✅ 追求处理速度
- ✅ 新手入门

### 选择Paraformer（说话人分离），如果：
- ✅ 视频有多人对话
- ✅ 需要区分不同说话人
- ✅ 追求播客质量
- ✅ 愿意配置OSS
- ✅ 内容是访谈或讨论类

---

## 模型切换

### 方法1：使用命令行参数（推荐）

**使用Qwen3-ASR**（不带说话人分离）：
```bash
python main.py full-pipeline video.mp4 --no-diarization
```

**使用Paraformer**（带说话人分离）：
```bash
python main.py full-pipeline video.mp4
# 或明确指定
python main.py full-pipeline video.mp4 --enable-diarization
```

### 方法2：分步执行

**使用Qwen3-ASR**：
```bash
# 步骤1：ASR转译（自动使用Qwen3-ASR）
python main.py asr video.mp4 -o asr.json

# 步骤2-6：后续处理步骤相同
python main.py process asr.json -o processed.json
python main.py translate processed.json -o translations.json
python main.py tts translations.json -m manifest.json
python main.py merge manifest.json -o final.mp3
```

**使用Paraformer**：
```bash
# 只能通过 full-pipeline 使用
python main.py full-pipeline video.mp4 -o final.mp3
```

---

## 技术细节

### Qwen3-ASR-Flash
- **API类型**：Recognition API（实时流式）
- **文件上传**：直接上传到DashScope
- **语言支持**：支持多语言混合（通过language_hints参数）
- **输出格式**：包含文本、时间戳
- **处理时间**：通常几分钟内完成

### Paraformer
- **API类型**：Transcription API（批处理）
- **文件上传**：必须先上传到OSS
- **说话人分离**：支持2-10个说话人
- **输出格式**：包含文本、时间戳、说话人ID
- **处理时间**：需要上传+处理，时间较长

---

## 常见问题

### Q1: 能否让Paraformer不使用说话人分离？
A: 技术上可以，但需要配置OSS。如果不需要说话人分离，建议直接使用Qwen3-ASR（更快更简单）。

### Q2: Qwen3-ASR能否区分说话人？
A: 不能。Qwen3-ASR的Recognition API不支持说话人分离功能。

### Q3: 两个模型的准确度如何？
A: 两个模型的ASR准确度都很高。Paraformer在处理多人对话时效果更好，因为能正确标记说话人。

### Q4: OSS费用如何？
A: OSS费用主要包括：
- 存储费用：极低（视频文件临时存储）
- 流量费用：上传免费，下载按流量计费
- 请求费用：可忽略不计
- **建议**：处理完成后可以手动删除OSS中的文件

### Q5: 如何选择说话人数量？
A:
- 如果知道准确数量：使用 `-s` 参数指定（如 `-s 2`）
- 如果不确定：不指定参数，让系统自动检测
- **注意**：说话人过多（>5人）可能影响准确度

### Q6: 能否自己实现Paraformer的本地文件支持？
A: 理论上可以，但需要：
1. 自己搭建文件服务器提供公开URL
2. 或使用其他对象存储服务
3. 修改 `paraformer_asr.py` 的上传逻辑

目前使用OSS是最简单稳定的方案。

---

## 未来计划

1. **性能优化**：研究更快的处理方式
2. **成本优化**：探索降低OSS成本的方法
3. **模型扩展**：支持更多ASR服务提供商
4. **自动选择**：根据内容自动选择最佳模型

---

## 参考文档

- [DashScope官方文档](https://dashscope.console.aliyun.com/)
- [Qwen3-ASR API文档](https://help.aliyun.com/document_detail/2712536.html)
- [Paraformer API文档](https://help.aliyun.com/document_detail/2712581.html)
- [阿里云OSS文档](https://help.aliyun.com/product/31815.html)

---

最后更新：2025-12-15
