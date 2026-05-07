import asyncio

# 场景：AI 正在滔滔不绝地说话 (TTS)，用户突然大喊一声“闭嘴！”
# 我们需要立即停止 TTS 的协程任务。这就是打断 (Interruption) 的核心。

async def ai_speaking():
    try:
        print("[AI] 正在念一段很长的话...")
        for i in range(1, 11):
            print(f"[AI] 说话中... ({i}/10)")
            await asyncio.sleep(0.5)
        print("[AI] 终于念完了。")
    except asyncio.CancelledError:
        # 当任务被 cancel() 时，会抛出这个异常。
        # 这里就是你清理资源（比如停止声卡播放、关闭 WebSocket）的地方。
        print("\n!!! [打断] 收到用户指令，AI 立即停止说话，清理资源中...")
        raise

async def user_interruption_trigger(speaking_task: asyncio.Task):
    """模拟 2 秒后用户突然说话"""
    await asyncio.sleep(2)
    print("\n[用户] (大喊): 别说了，听我说！")
    speaking_task.cancel() # 核心：取消任务

async def main():
    # 使用 create_task 将协程包装成一个可以被管理（取消）的任务
    speaking_task = asyncio.create_task(ai_speaking())
    
    # 模拟用户行为
    interruption_task = asyncio.create_task(user_interruption_trigger(speaking_task))
    
    try:
        await speaking_task
    except asyncio.CancelledError:
        print("[System] 会话状态已重置，现在进入收听模式。")

if __name__ == "__main__":
    asyncio.run(main())
