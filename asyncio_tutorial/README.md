# Asyncio 基础教程：Voice Agent 开发者专供

在构建语音 AI Agent 时，**异步编程 (Asyncio)** 是你最强大的武器。为什么？
- **音频流是持续的**：你需要一边听，一边转录，一边思考。
- **IO 密集型**：STT、LLM、TTS 几乎全是网络调用，等待响应时不能阻塞整个程序。
- **实时性要求极高**：打断逻辑要求程序能瞬间响应信号。

本教程通过 Voice Agent 的实际场景，带你从零掌握 `asyncio`。

---

## 目录
1. [01_hello_async.py](./01_hello_async.py) - 什么是协程？
2. [02_concurrent_tasks.py](./02_concurrent_tasks.py) - 如何同时处理多个 AI 模型？
3. [03_audio_pipeline.py](./03_audio_pipeline.py) - 使用 Queue 处理音频流数据。
4. [04_interruption_logic.py](./04_interruption_logic.py) - 核心：如何实现“打断”逻辑？

---

## 核心概念速览

### 1. 协程 (Coroutine)
不要把它看作普通的函数，把它看作一个**可以被挂起和恢复的任务**。
- `async def` 定义。
- `await` 挂起，等待耗时操作完成而不阻塞别人。

### 2. 事件循环 (Event Loop)
想象一个永不停歇的传送带。你把任务（协程）丢上去，当某个任务在等待（比如等 LLM 返回结果）时，传送带会转到下一个任务去执行。

### 3. 并发 (Concurrency) vs 并行 (Parallelism)
- **并发**：在同一时间内处理多个任务（在不同任务间快速切换）。Voice Agent 绝大多数场景是并发。
- **并行**：同一时刻真正同时运行（需要多核 CPU）。

---

## 准备工作
确保你安装了 Python 3.8+。

建议按顺序运行文件夹内的代码示例：
```bash
python asyncio_tutorial/01_hello_async.py
```
