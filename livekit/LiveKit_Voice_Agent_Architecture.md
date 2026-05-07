# LiveKit Voice Agent 架构设计报告

本报告详细介绍了 LiveKit Voice Agent 的设计原理、核心组件及其协作机制。该系统采用事件驱动、管道化和异步流式处理的设计模式，旨在提供低延迟、高可靠性的语音交互体验。

---

## 1. 核心架构设计

LiveKit Voice Agent 的架构可以概括为以下层次结构：

*   **AgentSession**: 会话层，负责管理与 LiveKit Room 的连接、房间 I/O（音频/视频/文本）、会话生命周期以及全局事件的分发。
*   **Agent**: 策略层，定义了 Agent 的“人格”（Instructions）、工具（Tools）以及核心组件（STT, LLM, TTS, VAD）的配置。它通过“节点”（Nodes）模式允许开发者自定义处理逻辑。
*   **AgentActivity**: 执行层，管理 Agent 在会话中的活跃状态。它负责协调音频识别输入和回复生成的输出。
*   **AudioRecognition**: 输入识别层，集成 VAD 和 STT，处理端点检测（Endpointing）和打断（Interruption）逻辑。
*   **SpeechHandle**: 响应单元，代表一次完整的助手回复任务，管理从文本生成到语音合成再到播放的整个生命周期。

---

## 2. 事件驱动与状态机

系统通过精细的状态切换和事件通知来保持组件间的同步。

### 2.1 状态定义
*   **UserState**: `speaking` (说话中), `listening` (听取中), `away` (离开/超时)。
*   **AgentState**: `initializing` (初始化), `idle` (空闲), `listening` (听取中), `thinking` (思考中/LLM 处理), `speaking` (说话中/TTS 播放)。

### 2.2 核心事件流
1.  **用户开始说话**: VAD 检测到音频 -> `AudioRecognition` 触发 `on_start_of_speech` -> `AgentSession` 更新 `UserState` 为 `speaking` -> 若 Agent 正在说话，触发打断逻辑。
2.  **转录进行中**: STT 持续产生 Interim/Final Transcripts -> `AudioRecognition` 更新转录缓存。
3.  **用户结束说话**: 端点检测算法（Endpointing）根据 VAD 信号和 STT 结果判定 turn 结束 -> 触发 `on_end_of_turn`。
4.  **生成回复**: `AgentActivity` 调用 `generate_reply` -> 创建 `SpeechHandle` -> 启动 LLM 处理任务。
5.  **思考与合成**: LLM 产生文本流 -> 同步输入 TTS 引擎 -> TTS 产生音频流。
6.  **播放**: 音频帧推送到 LiveKit 房间 -> `AgentSession` 更新 `AgentState` 为 `speaking`。

---

## 3. 核心组件协作机制

### 3.1 降噪 (AEC/Noise Cancellation)
降噪通常在 LiveKit SDK 层面或插件层面（如 `livekit-plugins-krisp`）处理。在 `AgentSession` 中，有一个 `aec_warmup_duration` 设置，用于在 Agent 开始说话初期的几秒内忽略打断，防止回声引起的误打断。

### 3.2 VAD (Voice Activity Detection)
VAD 是系统的“感官”：
*   它是音频处理管道的第一站。
*   它不仅用于检测静音，还驱动 `AudioRecognition` 中的端点检测计时器。
*   当 STT 不支持流式时，VAD 被用作 `StreamAdapter` 的触发器。

### 3.3 STT (Speech-To-Text)
STT 节点（`stt_node`）将音频帧转换为文本：
*   支持 Interim 结果以实现极速响应（Preemptive Generation）。
*   Final 结果用于最终确定用户意图并提交给 LLM。

### 3.4 LLM (Language Model)
LLM 节点（`llm_node`）负责逻辑处理：
*   处理 `ChatContext`（上下文管理）。
*   执行函数调用（Function Calling）。
*   流式输出文本 chunk，直接导向 TTS。

### 3.5 TTS (Text-To-Speech)
TTS 节点（`tts_node`）将文本转换为音频：
*   通常采用流式合成。
*   若 TTS 不支持流式，系统会自动使用句子分词器（Sentence Tokenizer）分段合成，平衡首包延迟（TTFB）和播放连贯性。

### 3.6 Turn-taking (轮流说话控制)
这是最复杂的逻辑，由 `AudioRecognition` 和 `endpointing.py` 协作完成：
*   **VAD 模式**: 仅依靠静音时长。
*   **STT 模式**: 结合 STT 的 end-of-speech 信号和静音时长。
*   **手动模式**: 允许完全由应用逻辑控制 turn 的切换。

---

## 4. 关键文件索引

*   `livekit/agents/voice/agent_session.py`: 顶层入口，状态中心。
*   `livekit/agents/voice/agent_activity.py`: 核心协调器，处理打断和任务调度。
*   `livekit/agents/voice/audio_recognition.py`: VAD 和 STT 的粘合剂，端点检测逻辑所在地。
*   `livekit/agents/voice/speech_handle.py`: 单次发言的生命周期管理。
*   `livekit/agents/voice/generation.py`: 定义了 LLM 和 TTS 的处理管道函数。
*   `livekit/agents/voice/endpointing.py`: 转场/结束说话的判定算法。

---

## 5. 设计原理总结

1.  **异步并发**: 所有的 I/O 和模型推理都是异步的，利用 `asyncio` 任务并发执行。
2.  **流式贯通**: 从 STT 到 LLM 再到 TTS，数据以 Stream 形式流动，最大化降低首字延迟。
3.  **弱耦合**: 通过 Node 抽象，开发者可以轻松替换任何一个 AI 模块，甚至插入自定义的中间件（如文本翻译、敏感词过滤）。
4.  **鲁棒性**: 具备自动重试机制、错误隔离（一个模型出错不崩溃整个会话）以及完善的指标监控（Telemetry）。
