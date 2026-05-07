import asyncio
import random

# 场景：音频数据是一帧一帧进来的。
# 我们需要一个“生产者”（录音）和一个“消费者”（播放/处理）。
# asyncio.Queue 是处理流式数据的最佳选择。

async def audio_producer(queue: asyncio.Queue):
    """模拟音频采集，每 0.5 秒产生一个音频块"""
    for i in range(5):
        audio_chunk = f"chunk_{i}"
        print(f"  [采集] 生成: {audio_chunk}")
        await queue.put(audio_chunk) # 放入队列
        await asyncio.sleep(0.5)
    
    await queue.put(None) # 放入结束标记

async def audio_consumer(queue: asyncio.Queue):
    """模拟音频处理，从队列中取数据"""
    print("[处理器] 等待数据中...")
    while True:
        chunk = await queue.get() # 从队列中取，如果队列为空会一直等着（不阻塞 CPU）
        if chunk is None:
            break
        
        print(f"  [处理器] 正在处理: {chunk}")
        # 模拟处理耗时
        await asyncio.sleep(random.uniform(0.1, 0.8))
        queue.task_done()
    
    print("[处理器] 处理完毕")

async def main():
    queue = asyncio.Queue()
    
    # 同时启动生产者和消费者
    # 即使处理速度有时慢于采集速度，队列也能起到缓冲作用。
    await asyncio.gather(
        audio_producer(queue),
        audio_consumer(queue)
    )

if __name__ == "__main__":
    asyncio.run(main())
