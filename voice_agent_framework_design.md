我已经将之前提到的所有建议（背压控制、并发广播、打断机制与队列清理、Frame数据结构抽象）融入了你的设计中。

这份代码更加接近工业级的流式语音 AI 框架（如 Pipecat），并且使用了优雅的 `asyncio` 异步模式。

### 完整实现代码

```python
import asyncio
from dataclasses import dataclass, field
from typing import Any, List, Optional
from abc import ABC, abstractmethod
from enum import Enum, auto

# ==========================================
# 1. 定义数据平面 (Data Plane): Frame 体系
# ==========================================
class Frame(ABC): 
    """数据流中的基本传递单元"""
    pass

@dataclass
class AudioFrame(Frame):
    audio_data: bytes

@dataclass
class TextFrame(Frame):
    text: str

class ControlFrame(Frame): 
    """控制帧，沿 Pipeline 传递的带内控制信号"""
    pass

class EndFrame(ControlFrame): 
    """结束标志，用于优雅关闭组件"""
    pass

class CancelFrame(ControlFrame):
    """取消当前生成的标志（打断处理用）"""
    pass

# ==========================================
# 2. 定义控制平面 (Control Plane): Event 体系
# ==========================================
class EventType(Enum):
    USER_STARTED_SPEAKING = auto() # VAD 检测到用户说话（打断）
    USER_STOPPED_SPEAKING = auto() # VAD 检测到用户停顿
    AGENT_STARTED_SPEAKING = auto()
    AGENT_STOPPED_SPEAKING = auto()

@dataclass
class VoiceAgentEvent:
    type: EventType
    data: Any = None

# ==========================================
# 3. 核心架构: Event Bus & Session
# ==========================================
class AgentSession:
    """管理全局控制平面 (Event Bus) 和组件生命周期"""
    def __init__(self):
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.components: List['PipelineComponent'] = []
    
    def register_component(self, component: 'PipelineComponent'):
        component.session = self
        self.components.append(component)
        
    async def emit(self, event: VoiceAgentEvent):
        """组件调用此方法向全局发送事件"""
        await self.event_queue.put(event)
        
    async def _broadcast(self, event: VoiceAgentEvent):
        """【改进 A】并发下发事件，防止单组件阻塞全局总线"""
        tasks = [component.handle_event(event) for component in self.components]
        # return_exceptions=True 防止某个组件的错误导致整个事件总线崩溃
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def run(self):
        """事件总线的主循环"""
        while True:
            event = await self.event_queue.get()
            await self._broadcast(event)
            self.event_queue.task_done()

# ==========================================
# 4. 核心架构: 管道组件
# ==========================================
class PipelineComponent(ABC):
    def __init__(self, name: str, queue_size: int = 100):
        self.name = name
        # 【改进 C】设置 maxsize 限制背压，防止生产远快于消费导致内存溢出和高延迟
        self.input_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.session: Optional[AgentSession] = None
        self.next_component: Optional['PipelineComponent'] = None
    
    def set_next(self, next_comp: 'PipelineComponent') -> 'PipelineComponent':
        """设置下一个节点，返回 next_comp 以支持链式调用 a.set_next(b).set_next(c)"""
        self.next_component = next_comp
        return next_comp
        
    async def push(self, frame: Frame):
        """向下游推送数据"""
        if self.next_component:
            await self.next_component.input_queue.put(frame)
            
    async def emit(self, event: VoiceAgentEvent):
        """向全局发送事件"""
        if self.session:
            await self.session.emit(event)

    def flush_queue(self):
        """【改进 B】立即清空当前队列（用于处理被打断的情况）"""
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
                self.input_queue.task_done()
            except asyncio.QueueEmpty:
                break

    @abstractmethod
    async def handle_event(self, event: VoiceAgentEvent):
        """处理来自 Session 的全局事件（比如响应打断）"""
        pass
        
    @abstractmethod
    async def process_frame(self, frame: Frame):
        """处理来自上游的数据帧"""
        pass
    
    async def run(self):
        """【改进 D】组件的独立异步任务循环"""
        while True:
            frame = await self.input_queue.get()
            
            if isinstance(frame, EndFrame):
                await self.push(frame) # 将关闭信号传递给下游
                self.input_queue.task_done()
                break
                
            try:
                await self.process_frame(frame)
            except asyncio.CancelledError:
                print(f"[{self.name}] 任务被取消 (打断)")
            except Exception as e:
                print(f"[{self.name}] 处理异常: {e}")
            finally:
                self.input_queue.task_done()
```

### 结合你的业务场景：如何使用这个框架？

下面我用一个 **打断（Interruption）** 的经典场景演示这个架构是如何运作的。假设你的 Pipeline 是 `STT -> LLM -> TTS`。

```python
class TTSComponent(PipelineComponent):
    def __init__(self):
        super().__init__(name="TTS")
        self._current_task = None

    async def handle_event(self, event: VoiceAgentEvent):
        # 如果检测到用户抢话，立刻停止当前的播报！
        if event.type == EventType.USER_STARTED_SPEAKING:
            print(f"[{self.name}] 收到打断信号，正在清理缓冲...")
            self.flush_queue() # 清空等待转换的文本
            # 停止当前正在生成的音频任务 (高级 asyncio 模式)
            if self._current_task and not self._current_task.done():
                self._current_task.cancel()
            
            # 通知下游（如扬声器组件）立刻停止播放
            await self.push(CancelFrame())

    async def process_frame(self, frame: Frame):
        if isinstance(frame, TextFrame):
            # 模拟耗时的文字转语音调用
            self._current_task = asyncio.create_task(self._synthesize(frame.text))
            try:
                audio_bytes = await self._current_task
                await self.push(AudioFrame(audio_bytes))
            except asyncio.CancelledError:
                # 任务被取消，安静退出
                raise

    async def _synthesize(self, text: str) -> bytes:
        print(f"[{self.name}] 开始合成: {text}")
        await asyncio.sleep(2) # 模拟网络延迟
        return b"fake_audio_data"

# ======= 运行示例 =======
async def main():
    session = AgentSession()
    
    # 实例化组件
    stt = PipelineComponent(name="STT") # 省略具体实现
    llm = PipelineComponent(name="LLM") # 省略具体实现
    tts = TTSComponent()
    
    # 注册到 Session (建立事件总线)
    session.register_component(stt)
    session.register_component(llm)
    session.register_component(tts)
    
    # 构建数据管道 (Data Pipeline)
    stt.set_next(llm).set_next(tts)
    
    # 启动所有任务
    tasks = [
        asyncio.create_task(session.run()),
        asyncio.create_task(stt.run()),
        asyncio.create_task(llm.run()),
        asyncio.create_task(tts.run())
    ]
    
    # 模拟推入一条文本给 TTS
    await tts.input_queue.put(TextFrame("你好，我是语音助手..."))
    
    # 模拟 0.5 秒后，用户突然打断
    await asyncio.sleep(0.5)
    await session.emit(VoiceAgentEvent(type=EventType.USER_STARTED_SPEAKING))
    
    # 等待一会儿观察日志
    await asyncio.sleep(1)

# 运行
# asyncio.run(main())
```

### 主要改进点总结 (Review Notes)

1. **`asyncio.gather` 解决阻塞**: 现在 `session._broadcast()` 不会因为一个卡住的节点而卡死整个大脑（Event Bus）了。
2. **分离 Frame 和 Event**: 数据用 `Frame` 顺着水管（Pipeline）流淌，控制信号用 `Event` 在空中（Session）广播。这是混合架构（Hybrid）的核心精髓。
3. **安全打断机制**: 增加了 `flush_queue()`，配合 `CancelFrame` 与 `asyncio.CancelledError` 的捕获，完美解决 LiveKit/Pipecat 都会面临的 “如何让 AI 马上闭嘴” 的痛点。
4. **背压防崩**: 给 Queue 加上 `maxsize=queue_size`。如果下游服务（比如 TTS 服务器）卡住，上游 LLM 生成再快也会被 `await put()` 阻塞，防止内存中堆积几千条消息，导致延迟呈指数级上升。
