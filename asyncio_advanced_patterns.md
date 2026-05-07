# Asyncio 高阶实战：任务编排、通信与优雅关闭

在 Voice Agent 中，你不仅仅是在运行一个协程，而是在指挥一个“交响乐团”：STT 负责听，LLM 负责想，TTS 负责说。这些任务必须**同时运行**、**互相配合**，并且在退出时**干干净净**。

---

## 1. 任务创建：`create_task` 的艺术

不要只是 `await` 一个协程，那会阻塞当前流程。使用 `asyncio.create_task` 让它在后台运行。

### 场景：同时启动 VAD 监控和心跳检测
```python
async def main_loop():
    # 启动后台任务，不阻塞 main_loop 的继续执行
    vad_task = asyncio.create_task(run_vad_monitor())
    heartbeat_task = asyncio.create_task(run_telemetry_heartbeat())
    
    # 任务现在已经在后台跑起来了
    print("系统已就绪，正在监控语音输入...")
    
    # 保持主循环运行
    await asyncio.gather(vad_task, heartbeat_task)
```

---

## 2. 任务间通信：状态同步

不同任务之间如何打招呼？比如：LLM 任务告诉 TTS 任务：“我已经生成好第一句了，你可以开始了”。

### 使用 `asyncio.Event` (信号灯)
`Event` 是最轻量级的同步工具。

```python
import asyncio

async def llm_generator(ready_event: asyncio.Event):
    print("[LLM] 正在思考...")
    await asyncio.sleep(2) # 模拟思考
    print("[LLM] 第一句生成好了！发送信号...")
    ready_event.set() # 拨动开关：绿灯亮起

async def tts_player(ready_event: asyncio.Event):
    print("[TTS] 准备就绪，等待 LLM 信号...")
    await ready_event.wait() # 阻塞在这里，直到收到 set() 信号
    print("[TTS] 收到信号！开始合成并播放音频流")

async def main():
    ready_event = asyncio.Event()
    await asyncio.gather(llm_generator(ready_event), tts_player(ready_event))
```

---

## 3. 任务的生命周期管理

在 Voice Agent 中，一个典型的任务（如 `SpeechHandle`）需要被跟踪，以便随时取消。

```python
class AgentSession:
    def __init__(self):
        self._tasks = set() # 使用集合存储活跃任务

    def start_task(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        # 任务完成后自动从集合中移除，防止内存泄漏
        task.add_done_callback(self._tasks.discard)
        return task
```

---

## 4. 优雅关闭 (Graceful Shutdown)

当用户挂断电话或程序异常退出时，你不能直接杀掉进程。你需要：
1.  停止录音。
2.  告诉云端 STT/TTS 结束会话。
3.  等待正在进行的写库操作完成。

### 核心模式：安全关闭所有任务
```python
async def shutdown(signal, loop):
    print(f"收到关闭信号 {signal.name}...")
    
    # 1. 找到所有还在运行的任务（排除当前 shutdown 任务本身）
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    print(f"正在取消 {len(tasks)} 个活跃任务...")
    for task in tasks:
        task.cancel()
    
    # 2. 给任务一点时间来处理 CancelledError (清理资源)
    # return_exceptions=True 保证即使某个清理逻辑报错，其他任务也能继续关闭
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("所有任务已关闭，清理完毕。")
    loop.stop()
```

---

## 5. 常见坑点 (Anti-Patterns)

### ❌ 坑 1: 忘记等待后台任务
如果你创建了 `create_task` 但主程序结束了，后台任务会瞬间被强杀，导致文件损坏或连接未正常关闭。
**对策**：始终确保在 `shutdown` 逻辑中等待所有任务结束。

### ❌ 坑 2: 任务中的异常消失了
如果一个后台任务崩溃了，除非你 `await` 它或检查它的 `exception()`，否则它可能在静默中死去。
**对策**：为重要的后台任务添加异常处理，或者使用 `task.add_done_callback` 记录错误日志。

```python
def handle_result(task):
    try:
        task.result()
    except Exception as e:
        print(f"任务崩溃了！错误: {e}")

task = asyncio.create_task(my_coro())
task.add_done_callback(handle_result)
```

---

## 总结：Voice Agent 的编排准则

1.  **解耦**：录音、识别、回复、播放应该是独立的后台任务。
2.  **信号驱动**：使用 `Event` 或 `Queue` 进行任务间协作，而不是互相调用。
3.  **安全取消**：每个协程都应该准备好处理 `CancelledError`。
4.  **彻底清理**：即使程序崩溃，也要通过 `try...finally` 确保音频设备被释放。
