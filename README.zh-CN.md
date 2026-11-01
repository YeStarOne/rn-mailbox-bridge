# rn-mailbox-bridge（中文说明）

给**任何** AI 一个 Reason Network 团队信箱——哪怕它不能跑工具、不能调 API、装不了插件。

单文件 Python 桥（纯标准库），替"只能读写文件"的 agent（比如 ChatGPT Work 这类桌面端）收发团队消息。接入后它就是**正式队员**：队友能给它发信、它能回信、它出现在团队列表里。

[English README](README.md)

```
              Reason Network 团队
  ┌──────────────────────────────────────────────┐
  │  队友 agent ──消息──> you/myagent            │
  └───────────────────────────────┬──────────────┘
                                  │  daemon 排队暂存（Pull 语义）
                                  ▼
        reason-network listen --as myagent   （长轮询，桥接代跑）
                                  │
                                  ▼
                      mailbox/inbox.md          （最新在最上，自动归档）
                                  │   你把文件喂给 AI
                                  ▼
                          无工具的 AI 读信
                                  ▲
                          AI 写回复
                                  │   （它不能写文件就由你代粘）
                                  ▼
                      mailbox/outbox.md         （第一行 = 收件人地址）
                                  │
                                  ▼
        reason-network send <to> --from myagent （桥接代跑）
```

## 为什么是文件桥

Reason Network 本来就支持"没有原生集成的 agent"：`reason-network listen --as <名字>` 会注册一个 **cli 会话**——真正的团队身份（`<人>/<名字>`，agent=cli），长轮询收信并标已读；`reason-network send <收件人> --from <名字>` 以该身份发信。**两个都是官方 CLI 的自带能力**——不需要 fork、不需要补丁、不动服务端。

桥接做的事只有一件：让这两条命令永远跑着，在它们和两个 markdown 文件之间搬文本。于是**任何能读文件的 AI 都能入队**：桌面助手、聊天窗口里的模型、沙箱里的受限模型，甚至一个偏爱邮件的人类队友。

## 信箱契约

| 方向 | 文件 | 格式 |
|---|---|---|
| 团队 → agent | `mailbox/inbox.md` | 桥接维护。最新来信在 `<!-- HEADER-END -->` 之后的顶部；旧信滚入 `inbox-archive.md`。每块是原始消息，带发件人标签。 |
| agent → 团队 | `mailbox/outbox.md` | 你/agent 创建。**第一行**：收件人地址——多个用空格或逗号隔开（`alice/dev bob/ops`），`*` 广播。**其余**：正文。 |

桥接监视 `outbox.md`，等它的大小+mtime 连续两轮不变才发（约 3–6 秒），半截文件永远不会被发出去。发出后归档到 `mailbox/sent/`；发不出的按原因留证为 `outbox-invalid-*.md` / `outbox-failed-*.md`。示例见 [examples/](examples/)。

## 快速开始

前置：装好 [reason-network CLI](https://github.com/reason-machines/reason-network) 并加入团队；Python 3.8+。

```bash
# 1. 给名为 "myagent" 的会话启动桥接
python bridge.py --session myagent

# 2. 任何队友（或任何有 RN 工具的 agent）发信
reason-network send you/myagent "hello from the team"
#   → 几秒内出现在 mailbox/inbox.md

# 3. 回信：保存 mailbox/outbox.md
#      第一行：you/队友会话名
#      其余：正文
#   → 几秒内送达，原件归档到 mailbox/sent/
```

把信箱交给 AI：把文件夹给它（拖 `inbox.md` 进对话，或把目录挂进它的工作区——看产品支持什么）。AI 完全不能写文件的话，你替它把回复粘进 `outbox.md` 即可——"人类当最后一公里"是设计的一部分，不是将就。

## 正经运行

* **7×24**：Windows 用 `pythonw bridge.py ...`（无窗口），其他平台用 launchd/systemd。加开机自启（Windows 比如 `HKCU\...\Run` 键）。
* **单实例**：按会话名派生本地端口锁。重复启动无害；两个**不同**会话的桥接可并存。
* **离线不丢信**：桥接（或机器）挂了，消息在 Reason Network daemon 排队，下次 `listen` 补收。
* **团队在册**：首次成功轮询后，桥接用 `reason-network hook cli doing ...` 挂状态，团队列表显示"mailbox bridge: standing by"。
* **日志**：`mailbox/bridge.log`（自动截断）。手动查：`reason-network who <会话>`；手动收：`reason-network listen --as <会话>`。

参数：`--session 名字`、`--mailbox 目录`、`--wait 秒`（长轮询，默认 600）、`--port N`、`--cli 路径`、`--addr 人/名字`（仅用于信箱头部展示）。也认 `RN_BRIDGE_SESSION` / `RN_TEAM` 环境变量。

## Windows 坑（实测换来）

* **pythonw 没有控制台，而它的控制台子进程会被 Windows 新开一个。** 在 `pythonw.exe` 下裸循环调 CLI，**每次轮询都弹一个新黑窗**；手关窗口会令 CLI 以 `0xC000013A` 退出，循环马上弹下一个——无限弹窗。桥接对每个子进程传 `subprocess.CREATE_NO_WINDOW`；自己写类似工具请照做。
* 不用 pythonw、直接在终端里跑 `python` 则无所谓；这个标志在其他平台是无操作。

## 多 agent 团队协作（playbook）

信箱只是一半——[docs/team-playbook.md](docs/team-playbook.md) 整理了让"混合团队"（多个 agent + 人）真正转起来的约定：谁负责什么的 roster、会话命名、五类消息（LOCK / PROGRESS / DONE / HANDOFF / ASK+ACK）、共享资源纪律，以及最重要的一条：*任务跟别人重叠时，先 ASK 再动手*。

## 局限

* **agent 侧非实时**：无工具的 AI 什么时候"读到信"取决于你何时喂文件。急事别走它。
* **无唤醒**：cli 会话永不被主动戳，只靠轮询。这是设计使然（上游唤醒桥也把它们过滤掉了）。
* **只走文件**：>64MB 附件走 Reason Network 的审批流，不走信箱；让队友改发共享盘。

## 相关

* [reason-machines/reason-network](https://github.com/reason-machines/reason-network) —— 本项目桥接的引擎（MIT OR Apache-2.0）。`listen --as`、`send --from`、`hook` 都是上游自带能力。
* DeepSeek Harness 团队《Super-agent 设计探索》（2026-10）——用同一批积木（事件驱动信箱、常驻本地 daemon、离线补收）构建自家的多智能体体系，独立验证了这个方向。想看模式往哪走值得一读。

## 许可

MIT —— 见 [LICENSE](LICENSE)。
