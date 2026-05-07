import asyncio
import time

# 场景：我们需要同时调用 STT (语音转文字) 和 LLM (大模型)
# 如果是同步编程，你得等 STT 完了再开始 LLM。
# 异步编程可以让它们“看起来”像是在一起跑。

async def stt_service():
    print("[STT] 正在监听音频...")
    await asyncio.sleep(3) # 模拟 3 秒的录音和识别
    print("[STT] 识别成功: '今天天气怎么样？'")
    return "今天天气怎么样？"

async def llm_warmup():
    print("[LLM] 正在预热模型缓存...")
    await asyncio.sleep(1) # 模拟模型预热
    print("[LLM] 预热完成")
    return "Ready"

async def main():
    start_time = time.perf_counter()
    
    print("--- 并发执行开始 ---")
    
    # 使用 asyncio.gather 同时运行多个任务
    # 它们会同时开始，总耗时取决于最慢的那个任务（3秒），而不是加起来（4秒）。
    results = await asyncio.gather(
        stt_service(),
        llm_warmup()
    )
    
    print(f"所有任务结果: {results}")
    
    end_time = time.perf_counter()
    print(f"总耗时: {end_time - start_time:.2f} 秒 (如果是同步则需要 4 秒)")

if __name__ == "__main__":
    asyncio.run(main())
