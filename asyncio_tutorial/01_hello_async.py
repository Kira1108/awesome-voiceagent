import asyncio
import time

# 场景：模拟一个简单的 TTS (文字转语音) 调用
# 普通函数会阻塞整个程序，而协程允许在等待时让出控制权。

async def simulate_tts(text: str):
    print(f"[TTS] 开始合成: '{text}'...")
    # await 是关键！它告诉程序：这里有耗时 IO，你去干别的吧，好了叫我。
    await asyncio.sleep(2) 
    print(f"[TTS] 合成完毕: '{text}'")
    return f"audio_data_of_{text}"

async def main():
    start_time = time.perf_counter()
    
    # 调用协程必须使用 await
    print("--- 任务 1 开始 ---")
    audio = await simulate_tts("你好，我是 AI 助手")
    print(f"获得数据: {audio}")
    
    end_time = time.perf_counter()
    print(f"总耗时: {end_time - start_time:.2f} 秒")

if __name__ == "__main__":
    # 运行异步程序的入口
    asyncio.run(main())
