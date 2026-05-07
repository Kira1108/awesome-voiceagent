import asyncio
import time
import random
from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    LISTENING = auto()
    PENDING_EOU = auto()
    THINKING = auto()
    SPEAKING = auto()


class EOUDecision(Enum):
    CONTINUE = auto()  # 用户没说完，继续听
    FINISHED = auto()  # 用户说完了，可以回复
    UNCERTAIN = auto() # 不确定，等待更多信号


class VoiceAgentArbiter:
    """
    状态机仲裁器：负责协调 VAD 物理信号与 EOU 认知判决。
    """
    def __init__(self):
        self.state = State.IDLE
        self.lock = asyncio.Lock()
        self.pending_eou_task = None   # 跟踪当前 EOU 仲裁任务
        self.current_llm_task = None
        self.last_vad_update = time.time()

        # 模拟配置
        self.vad_silence_threshold = 0.8  # 秒
        self.eou_wait_timeout = 0.4      # PENDING_EOU 态等待 EOU 判决的时间

    def _log_event(self, event_type: str, detail: str, old_state: State = None, new_state: State = None):
        """结构化事件日志"""
        ts = time.strftime("%H:%M:%S", time.localtime())
        state_info = ""
        if old_state and new_state:
            state_info = f" | {old_state.name} -> {new_state.name}"
        elif old_state:
            state_info = f" | state={old_state.name}"
        print(f"[{ts}] [{event_type}]{state_info} | {detail}")

    async def transition(self, new_state: State):
        """
        状态转换：先在锁内完成状态变更，再在锁外执行副作用，
        避免 asyncio.Lock（不可重入）导致的死锁。
        """
        async with self.lock:
            if self.state == new_state:
                return
            old_state = self.state
            self.state = new_state
            self._log_event("TRANSITION", f"状态切换完成", old_state, new_state)

        # 副作用在锁外执行，防止死锁
        if new_state == State.LISTENING:
            await self._on_enter_listening()
        elif new_state == State.THINKING:
            await self._on_enter_thinking()
        elif new_state == State.SPEAKING:
            await self._on_enter_speaking()

    async def _on_enter_listening(self):
        # 取消进行中的 EOU 仲裁任务
        if self.pending_eou_task and not self.pending_eou_task.done():
            self.pending_eou_task.cancel()
            self._log_event("ACTION", "取消进行中的 EOU 仲裁任务")
            self.pending_eou_task = None

        # 如果正在说话/思考，立即打断
        if self.current_llm_task and not self.current_llm_task.done():
            self._log_event("ACTION", "用户开始说话，打断 LLM/TTS 任务")
            self.current_llm_task.cancel()
            self.current_llm_task = None
        self._log_event("ACTION", "开启 STT 流式采集...")

    async def _on_enter_thinking(self):
        self._log_event("ACTION", "提交最终文本到 LLM...")
        self.current_llm_task = asyncio.create_task(self._simulate_llm_response())

    async def _on_enter_speaking(self):
        self._log_event("ACTION", "开启音频播放器推送流...")

    async def _simulate_llm_response(self):
        try:
            self._log_event("LLM", "正在思考中...")
            await asyncio.sleep(1.5) # 模拟推理延迟
            await self.transition(State.SPEAKING)
            self._log_event("TTS", "正在播放回答: '你好，我是你的 AI 助手。'")
            await asyncio.sleep(3.0) # 模拟播放耗时
            await self.transition(State.IDLE)
        except asyncio.CancelledError:
            self._log_event("LLM/TTS", "任务已成功取消并清理资源。")
            raise

    # --- 外部事件接口 ---

    async def on_vad_start(self):
        """VAD 检测到有效声音"""
        self._log_event("EVENT", f"VAD_START | 当前状态: {self.state.name}")
        if self.state in [State.IDLE, State.SPEAKING, State.PENDING_EOU, State.THINKING]:
            await self.transition(State.LISTENING)

    async def on_vad_silence(self):
        """VAD 检测到静音"""
        if self.state == State.LISTENING:
            self._log_event("EVENT", "VAD_SILENCE 触发 | 进入 PENDING_EOU 判定环节")
            await self.transition(State.PENDING_EOU)
            # 启动 EOU 仲裁逻辑，保存任务引用以便后续取消
            self.pending_eou_task = asyncio.create_task(self._arbite_eou())

    async def _arbite_eou(self):
        """模拟 EOU 模型决策过程，带超时保护"""
        try:
            self._log_event("EOU", "正在分析语气与语义...")

            # 使用超时保护，防止 EOU 模型挂起导致状态机卡死
            try:
                await asyncio.wait_for(
                    asyncio.sleep(0.3),  # 模拟模型推理耗时
                    timeout=self.eou_wait_timeout,
                )
            except asyncio.TimeoutError:
                self._log_event("EOU", "EOU 判决超时，默认视为用户说完 -> THINKING")
                async with self.lock:
                    if self.state != State.PENDING_EOU:
                        return
                await self.transition(State.THINKING)
                return

            # 模拟决策逻辑：50% 概率认为用户没说完
            decision = random.choice([EOUDecision.CONTINUE, EOUDecision.FINISHED])

            # 在锁内检查状态，但不调用 transition（避免死锁）
            async with self.lock:
                if self.state != State.PENDING_EOU:
                    self._log_event("EOU", "状态已改变（用户又说话了），丢弃本次判决")
                    return  # 状态已改变（例如用户又突然说话了）
                # 只记录决策，不在锁内做状态转换
                next_state = None
                if decision == EOUDecision.CONTINUE:
                    self._log_event("EOU", "Decision: NOT_FINISHED (用户在思考) -> 重置 VAD 监听")
                    next_state = State.LISTENING
                else:
                    self._log_event("EOU", "Decision: FINISHED (确认说完了) -> 推进到 THINKING")
                    next_state = State.THINKING

            # 在锁外执行状态转换
            if next_state:
                await self.transition(next_state)

        except asyncio.CancelledError:
            self._log_event("EOU", "EOU 仲裁任务被取消（用户重新开始说话）")
            raise


async def main():
    arbiter = VoiceAgentArbiter()

    print("=" * 50)
    print("=== 场景 1: 正常对话 ===")
    print("=" * 50)
    await arbiter.on_vad_start()
    await asyncio.sleep(1.0)
    await arbiter.on_vad_silence()
    await asyncio.sleep(6.0) # 等待思考和播放完成

    print()
    print("=" * 50)
    print("=== 场景 2: 用户犹豫，EOU 修正状态 ===")
    print("=" * 50)
    await arbiter.on_vad_start()
    await asyncio.sleep(0.5)
    await arbiter.on_vad_silence() # 此时 EOU 可能会强制回到 LISTENING

    await asyncio.sleep(8.0)

if __name__ == "__main__":
    asyncio.run(main())
