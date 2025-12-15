以下是我的需求：
【角色】你是资深的AI产品经理及全栈工程师
【目标】我希望实现一个能对视频（如youtube）转译为中文音频的AI产品应用，用于制作播客使用，该工具转译后的中文音频自然流畅，且像真人对话。
【参考思路环节】
整体框架思路：
通过cookie单独获取视频/音频 -> 上传视频/音频 -> ASR转译 -> LLM翻译与润色 -> TTS转中文语音
环节1、把youtube地址获取视频的环节剥离，应用本身只支持上传视频、音频。关于怎么通过地址获取视频，你给我写个python，通过此python代码并基于cookie（见chorme扩展程序Get cookies.txt LOCALLY）来获取。‘
 
环节2、对步骤1的视频使用通义听悟模型进行ASR转译。通义听悟接口文档地址：https://help.aliyun.com/zh/tingwu/api-tingwu-2023-09-30-overview?spm=a2c4g.11186623.0.i0
 
环节3、使用gemini 2.5pro模型将步骤2转译后的内容翻译为中文，过程中通过gemini 2.5pro模型在翻译后的中文内容中增加语气词使得内容更像人的对话。
 
环节4、使用gemini 2.5 preview TTS audio模型将步骤3中的文字内容进行TTS 生成语音。gemini 2.5 preview TTS audio接口文档：https://ai.google.dev/gemini-api/docs/models?hl=zh-cn#gemini-2.5-pro-tts
 
【主要注意点】
（1）ASR结果用正则去做下预处理，预处理包括只保留有效字段，如text、speaker，以及针对超长结果做切分（这是考虑下个环节模型的输出上限）
（2）翻译：可以批量处理（如3-5段），保持上下文连贯
（3）如果前面是分段翻译的，TTS环节需考虑按顺序合成一个完整的音频。

【apikey】
通义听悟 apikey : sk-d086548cbf5545c29159fb5bffb2e9e1
gemini apikey: AIzaSyBdypFvt_4lct0CDjTG4ZVwefMHfyBpv2o