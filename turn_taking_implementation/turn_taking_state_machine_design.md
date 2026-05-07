# Advanced Turn-Taking & EOU State Machine Design

在现代 Voice Agent 架构中，**Turn-taking（控场逻辑）** 不再仅仅是 VAD（声音检测）的简单开关，而是一个由 **EOU (End of Utterance) 模型** 驱动的认知决策过程。EOU 负责解析声音的物理属性、语义完整性以及社交节奏，从而动态修改或覆盖 VAD 的状态判决。

---

## 1. 核心五状态模型 (5-State Model)

为了支持复杂的 EOU 逻辑，我们将状态机扩展为五个核心状态：

| 状态 | 描述 | EOU 的作用 |
| :--- | :--- | :--- |
| **`IDLE`** | 初始状态，等待唤醒或首声。 | 监控背景噪音阈值，辅助 VAD 动态调优。 |
| **`LISTENING`** | 用户正在说话，持续采集音频/流式 STT。 | 实时分析中间文本/声音语气，判断是否有“抢话”倾向。 |
| **`PENDING_EOU`** | **核心缓冲态**。VAD 已静音，等待 EOU 裁决。 | 决定是 `FLUSH`（结束）还是 `RESET`（判定为中途停顿）。 |
| **`THINKING`** | EOU 确认结束。LLM 正在推理，TTS 正在首包合成。 | 允许被新 VAD 信号极速打断并抛弃当前任务。 |
| **`SPEAKING`** | 助手正在播放音频。 | 区分“有效打断”与“背景杂音”，决定是否执行 Barge-in。 |

---

## 2. 四大架构下的 EOU 逻辑详解

### 架构 A：VAD -> STT -> EOU (Text-based) -> LLM -> TTS
**核心逻辑**：语义驱动，防止断在半截话上。
- **EOU 输入**：流式 STT 的 Interim/Final 文本。
- **状态修改场景**：
    - **Case 1 (用户犹豫)**：VAD 静音 800ms，但文本是“我想要订一个...”。EOU 返回 `NOT_FINISHED`。
    - **动作**：状态机发送 `RESUME` 给 VAD，强制重置计时器，状态停留在 `LISTENING`。
    - **Case 2 (快速确认)**：用户只说了一个“好”。语义已完整。
    - **动作**：无视 VAD 的 800ms 阈值，立即（200ms）切换到 `THINKING`。

### 架构 B：VAD -> EOU (Acoustic-based) -> STT -> LLM -> TTS
**核心逻辑**：语气驱动，响应比文本更快。
- **EOU 输入**：音频的基频 (F0)、能量包络、语调变化。
- **状态修改场景**：
    - **Case 1 (疑问语调)**：用户语调上扬。EOU 判定为 `QUESTION_END`。
    - **动作**：即便 VAD 还在检测微弱尾音，直接 `CUT_OFF` 录音流，启动响应。
    - **Case 2 (沉思语气)**：用户发出“呃...”或长拖音。EOU 判定为 `THINKING_ALOUD`。
    - **动作**：覆盖 VAD 状态，向用户播放极短的“提示音（Mmm-hmm）”以示在线，但不触发 LLM。

### 架构 C：STT API (Partial signals) -> EOU Controller -> LLM -> TTS
**核心逻辑**：利用云端预测信号，多级预热。
- **EOU 输入**：API 返回的 `Partial_Result` (0/1/2) 和 `Endpoint_Confidence`。
- **状态修改场景**：
    - **Partial 1 (预热)**：收到关键字。状态机进入 `PRE_THINKING`，LLM 开始拉取 Context，但不生成文字。
    - **Partial 2 (预测结束)**：API 认为话快说完了。
    - **动作**：状态机提前 300ms 停止播放器的打断监听，准备无缝衔接语音输出。

### 架构 D：VAD -> Multimodal (Audio-in) -> EOU (Internal) -> VAD
**核心逻辑**：原生多模态，社交直觉化。
- **EOU 输入**：模型内部产生的 `Probability_of_Turn_End` 连续流。
- **状态修改场景**：
    - **跨模态同步**：模型在听的同时，内部 EOU 模块在预测下一个 Token 是否为 `[END_OF_TURN]`。
    - **状态修改**：一旦预测概率 > 0.9，状态机立即将 VAD 模式切换为 `Barge-in_ONLY`（只听打断），并触发 TTS 输出。

---

## 3. 各种异常与复杂情况处理 (Scenario Matrix)

| 场景 | 事件输入 | 状态机决策动作 |
| :--- | :--- | :--- |
| **中途停顿 (Thinking Pause)** | VAD: Silence(600ms), EOU: `CONTINUE` | 状态机发送 `RESET_VAD`，维持 `LISTENING`。 |
| **环境嘈杂 (Noise spike)** | VAD: Audio_Start, EOU: `NON_HUMAN` | 状态机忽略该 VAD 信号，维持 `SPEAKING` 或 `IDLE`。 |
| **突发打断 (Barge-in)** | VAD: Audio_Start, EOU: `VALID_SPEECH` | 状态机执行 `Player.Stop()`，Cancel `LLM_Task`，强制切回 `LISTENING`。 |
| **假结束 (False end)** | VAD: Silence, EOU: `FINISHED` (但随后 200ms 又有声) | 状态机执行 `Rollback`：停止正在生成的任务，将旧文本与新音频合并。 |
| **助手抢话 (Assistant Interject)** | 系统事件: `URGENT_NOTIF` | 状态机在 `LISTENING` 态下强制切换到 `SPEAKING`，EOU 辅助生成“抱歉打断一下”。 |

---

## 4. 给开发者的实现建议

1.  **解耦 Arbiter (仲裁器)**：不要在 VAD 模块写逻辑。建立一个 `TurnManager` 类，作为 VAD 和 EOU 的裁判。
2.  **动态阈值**：EOU 应该能根据当前对话的上下文（Context）修改 VAD 的 `min_silence_duration`。
    - 闲聊模式：1.2s（给用户留出思考时间）。
    - 指令模式：0.5s（极速响应）。
3.  **状态追踪日志**：在日志中必须记录 `State: PENDING_EOU -> Decision: RESET by EOU_Text_Model`，否则无法排查"为什么 AI 没反应"或"为什么 AI 乱抢话"。推荐格式：`[时间戳] [事件类型] | 旧状态 -> 新状态 | 详情`。
4.  **避免锁死锁 (Lock Deadlock)**：`asyncio.Lock` **不可重入**。如果 `transition()` 持锁后调用 `_on_enter_thinking()`，而后者最终又调用 `transition()`，将导致永久挂起。
    - **规则**：锁内只做状态读写，所有副作用（启动任务、取消任务、调用外部模块）必须在锁外执行。
    - **模式**：
      ```python
      async with self.lock:
          old, self.state = self.state, new_state  # 锁内：纯状态变更
      await self._on_enter_xxx()                   # 锁外：副作用
      ```
5.  **EOU 超时保护**：EOU 模型可能因网络或计算问题卡住。必须用 `asyncio.wait_for()` 包裹 EOU 调用，超时后默认走 `FINISHED` 路径进入 `THINKING`，避免状态机在 `PENDING_EOU` 永久挂起。
6.  **任务生命周期管理**：所有通过 `asyncio.create_task()` 创建的异步任务（EOU 仲裁、LLM 推理、TTS 播放）必须：
    - 保存引用（如 `self.pending_eou_task`），不可 fire-and-forget。
    - 在状态转换时检查 `.done()` 并主动 `.cancel()`。
    - 在任务内部处理 `CancelledError` 并清理资源。
7.  **EOU 竞态防护**：用户快速"说→停→说→停"时，多个 `_arbite_eou` 任务可能并发执行。进入 `LISTENING` 态时必须取消旧的 EOU 任务，并在 EOU 任务返回时重新校验当前状态是否仍为 `PENDING_EOU`。
