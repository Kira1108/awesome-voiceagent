<p align="center">
  <img src="assets/banner.png" alt="Awesome Voice Agent Banner" width="800"/>
</p>

<h1 align="center">🎙️ Awesome-Voice Agent</h1>

<p align="center">
  <em>Analyze open-source voice agent frameworks, including Pipecat and LiveKit Agents, and provide a comprehensive comparison of their design patterns, architectures, and use cases.</em>
</p>

<p align="center">
  <a href="#-project-structure">Structure</a> •
  <a href="#-topics-covered">Topics</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="#-license">License</a>
</p>

---

## 📁 Project Structure

```
awesome-voiceagent/
├── README.md
├── Voice_Agent_Developer_Learning_Path_CN.md   # 开发者学习路径
├── audio_basics.md                             # 音频基础知识
├── asyncio_advanced_patterns.md                # asyncio 高级模式
├── asyncio_tutorial/                           # asyncio 教程
├── state_machine_guide.md                      # 状态机设计指南
├── livekit/                                    # LiveKit Agents 分析
├── pipecat/                                    # Pipecat 框架分析
├── livekit-vs-pipecat.md                       # 框架对比
└── turn_taking_implementation/                 # Turn-Taking 状态机实现
    ├── turn_taking_state_machine_design.md      # EOU 状态机设计文档
    └── voice_agent_fsm.py                       # 五状态 FSM 原型代码
```

## 📚 Topics Covered

| Topic | Description |
| :--- | :--- |
| **Framework Comparison** | Pipecat vs LiveKit Agents — architecture, pipeline design, and tradeoffs |
| **Turn-Taking & EOU** | Advanced 5-state FSM with VAD + EOU (End of Utterance) arbitration |
| **Audio Fundamentals** | Sample rates, PCM encoding, audio buffering, and streaming basics |
| **Async Patterns** | `asyncio` deep dive — task management, cancellation, and concurrency patterns for real-time voice |
| **State Machine Design** | General-purpose FSM patterns applied to voice agent control flow |

