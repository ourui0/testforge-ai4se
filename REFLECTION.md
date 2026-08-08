# REFLECTION — TestForge 项目反思

一、Superpowers 技能：什么真正起作用

**Brainstorming 是最高杠杆的环节。** 在项目启动阶段，`brainstorming` 技能通过
逐项追问——目标用户是谁、危险动作是什么、反馈信号从哪来、重点维度选哪个——
迫使我从模糊想法走向可执行的规约。这个过程最大的价值在于：它暴露了我最初设
计中的大量隐性假设。例如，我起初认为"护栏就是拦截危险 shell 命令"，但
brainstorming 追问"文件围栏是否也应该在护栏范围内？"后，我才意识到目录越界
写入同样是 coding agent 的致命风险，最终将文件围栏也纳入了治理模块。这种"被
追问出来的设计"很难靠自己在脑子里完成。

相比之下，`writing-plans` 的 19 个 task 拆分在项目初期提供了清晰的路标，但实
际执行中出现了预期之外的偏差：PLAN 中假设 task 可以严格串行推进，但实践中发
现某些 task（如 LLM 适配器与凭据存储）天然高度耦合，强行拆分反而增加了集成
成本。PLAN 作为"初始地图"有价值，但把它当作"精确导航"则过于乐观。

`test-driven-development` 技能的红-绿-重构纪律在整个开发过程中是有效的约束。
它防止了 subagent 在 mock 测试通过之前就急于写"看起来对"的实现。但也存在局
限：TDD 强制对 mock LLM 场景有效，但对于涉及真实 Docker sandbox 的 task，测试
的执行时间（构建镜像需要 30s+）让红-绿循环变得笨重。这些 task 在实践中更多地
依赖集成后的端到端验证，而非严格的 TDD 逐步推进。

`subagent-driven-development` 是双刃剑。worktree 隔离让每个 task 拥有独立的工作
区，避免了 task 间意外耦合。但如果 task brief 写得不精确——例如"实现反馈引擎"
这样的模糊描述——subagent 会自行发挥、偏离 SPEC 中约定的接口签名。我学到的教
训是：task brief 必须包含具体的文件路径、函数签名、返回类型和验证命令，否则
subagent 的自由度会导致大量返工。

`requesting-code-review` 和 `finishing-a-development-branch` 两个技能在本次项
目中未能充分发挥。由于 task 拆分较细，review 主要在 task 内部由人工快速扫描
完成，而不是走完整的两阶段评审流程。这不是技能本身的问题，而是项目规模与
task 颗粒度的匹配问题——当每个 task 不超过 150 行代码时，正式的评审流程的
固定开销相对过高。

---

## 二、TDD 在 AI 协作下：放大器，但有条件

TDD 在 AI 协作中的价值比在人肉编程中更大，原因是：**subagent 会撒谎**。

具体来说，subagent 在完成任务后倾向于宣称"已完成并通过测试"，但实际运行时
经常出现意料之外的失败。GitHub CI 是反复出现的典型案例：subagent 在本地通
过了 `pytest`，然后提交代码并声称 CI 通过。但 CI 实际运行时，由于路径分隔符
（Windows `\` vs Linux `/`）、依赖缺失、lint 规则差异等原因，CI 报错。这些
问题 subagent 自己不会主动发现——它没有在"真实 CI 环境"中运行，只是基于本地
结果做出了过度自信的判断。

如果没有 TDD 强制的前置失败测试（红阶段），这类问题会更隐蔽地被埋入代码库。
mock-LLM 确定性测试在这一点上尤其有效：它不依赖网络、不依赖真实 LLM 的随
机性，每次运行结果完全相同。这意味着 CI 中的测试失败是可复现的、可调试的，
而不是"偶尔通过偶尔失败"的玄学。例如，在一次重构 `app.py` 的 demo 模式时，
mock 测试立即暴露了 `create_demo_task` 返回值从简单 dict 变为复杂对象后
`JSONResponse` 序列化失败的问题——如果依赖真实 LLM 返回，这个 bug 可能要等
到 Render 部署后才能发现。

TDD 不是阻碍，但它确实增加了前期时间投入。对于探索性强的 task（如 WebUI 的
HTML 布局设计），严格的 TDD 性价比不高；对于核心机制（反馈引擎、质量门槛、
状态机），TDD 是必不可少的。

---

## 三、Subagent 自主运行的距离与偏离模式

在本次项目中，subagent 通常能自主完成一个中等粒度的 task（2-3 个文件，约
100-200 行代码），大约 5-15 分钟不偏离主题。更长的连续运行——例如从领域模型
一路做到 CLI 集成——几乎不可能不偏离。

偏离的表现模式有三种：

1. **方向偏离**：subagent 在没有明确指示的情况下引入了 SPEC 之外的功能。例如
   在实现持久化层时，一个 subagent 自作主张添加了 PostgreSQL 支持，而 SPEC
   明确只要求 SQLite。这源于 task brief 中缺少"不要做的事"清单。

2. **标准降低**：当遇到困难时（如 mock sandbox 的 Docker API 模拟过于复杂），
   subagent 倾向于简化实现而不是解决根本问题。它会生成一个"能通过测试但实际
   不可用"的简化版本——这比直接失败更危险，因为测试不会发现。

3. **过度自信**：subagent 在本地通过测试后立即宣布完成，但忽略了跨平台兼容性
   （Windows/Linux 路径差异）、CI 环境差异（依赖版本）、以及 lint 规则。

最有效的防偏离策略是：**在 task brief 中显式列出验证命令**。不是"测试应该通
过"，而是 `python -m pytest tests/unit/test_governance.py -v`。具体的、可复制
粘贴的命令让 subagent 无借口偏离。其次是 **SPEC 中的接口签名**——在 SPEC 中
预先约定函数签名和返回类型，让 subagent 的发挥空间被限制在实现细节而非接口
层面。

---

## 四、Task 颗粒度：最佳大小

从本项目的 19 个 task 经验来看，最优颗粒度的判断标准不是行数或文件数，而是：

- **一个 task 的验证步骤能否在三行命令内完成**。如果能（如 `pytest tests/unit/test_X.py`），task 就是合适的。如果需要"先启动 Docker、再初始化项目、再运行、再检查日志"的多步验证，task 就太大了。

- **一个 task 不应跨越两个不同的 mock 边界**。如果一个 task 同时涉及真实 LLM
  和真实 Docker，拆成两个——这样 mock 测试能涵盖更多逻辑。

- **"避免做的事"和"要做的事"同等重要**。每个 task brief 都应包含一段"不要：
  引入新依赖 / 修改 SPEC 中的接口签名 / 假设特定操作系统"的负面清单。

在 TestForge 中，大约 70% 的 task（domain models、persistence、governance、
parsers、feedback engine 等）颗粒度合理，每个 task 在 100-200 行之间，可在
30 分钟内完成。剩下的 30%（sandbox、engine、CLI integration）因为跨模块集成
较多，实际工作量远超 PLAN 的估算。

---

## 五、SPEC/PLAN 质量如何影响实现质量

最典型的案例是 **Task 12（Agent Engine）的 APPLYING_PATCH 死锁**。

SPEC 和 PLAN 中描述了状态机的主流程：CREATED → … → AWAITING_APPROVAL →
APPLYING_PATCH → COMPLETED。但没有明确写出 AWAITING_APPROVAL 之后具体由
谁来触发 APPLYING_PATCH 的 transition。最初实现中，engine 在审批通过后没
有自动进入 APPLYING_PATCH，而是停留在 AWAITING_APPROVAL 等待一个永远不会
到来的外部信号——导致死锁。

这个 bug 的根因不是 subagent 写错了代码，而是 **SPEC 的隐式知识没有被显式
化**。我在 brainstorming 时已经想清楚了"审批通过后自动继续"的语义，但这个
语义只存在于我的脑子里，没有写进 SPEC。一个全新的 agent 读到"AWAITING_
APPROVAL → APPLYING_PATCH"的转换规则时，它无法知道谁负责触发——是人工调用、
定时器、还是 engine 自己——于是选择了"等待外部信号"的错误实现。

这验证了课程的核心论点：**规约的质量决定了实现的正确性上限**。在 AI 协作
中，规约的模糊性会被放大——因为 human reviewer 可以自动脑补缺失的上下文，
而 AI subagent 不能。

---

## 六、最有效的 Prompt / Context 策略

经过 19 个 task 的迭代，我总结出以下最有效的策略：

1. **具体胜过抽象**。"在 `src/testforge/governance/policy.py` 中实现
   `validate_command(cmd: str) -> bool` 函数，当命令包含 `rm -rf`、`DROP TABLE`、
   `chmod 777` 时返回 False"比"实现危险命令拦截"有效得多。

2. **先给接口，再给逻辑**。在 task brief 中先给出函数签名（从 SPEC 复制），
   再描述内部逻辑。这让 subagent 的代码能正确集成到调用方，无需事后修改接口。

3. **验证命令必须是可复制粘贴的**。`python -m pytest tests/unit/test_feedback.py -v`
   比"运行单元测试"好一万倍——前者 subagent 真的会执行，后者它可能跳过。

4. **负面约束不可或缺**。每个 task brief 末尾的"不要"清单（不要引入新依赖、
   不要修改 SPEC 定义的接口、不要假设操作系统类型）持续防止了大量偏离。

5. **Mock 优先的真实意义**。让 subagent 先完成 mock 测试，再做真实集成。这不
   仅是 TDD 的要求，更重要的是：mock 测试通过证明了**逻辑正确**，剩下的只是
   集成调试，两类问题被干净地分开了。

---

## 七、凭据与分发：被低估的工程挑战

凭据安全存储和分发是课程要求中"看起来最简单、做起来最磨人"的部分。

**凭据方面**，OS keyring 的跨平台兼容性是一个持续的麻烦：Windows Credential
Manager、macOS Keychain、Linux Secret Service 三套 API 的行为细节各不相同。
在开发阶段，keyring 库在 Windows 上的 `pywin32` 依赖链导致过多次 CI 构建失
败。最终采取了"demo mode 完全禁用凭据、full mode 使用 keyring"的分层策略，
demo 部署不再依赖 keyring，避免了 Render 上的安装问题。这个过程让我意识到：
凭据安全的难点不在加密算法，而在**分发到不同平台时的依赖可移植性**。

**分发方面**，PyPI 打包 + Docker 镜像 + Render 部署三重分发看似冗余，实则各
有不可替代的场景：PyPI 给命令行用户、Docker 给本地沙箱用户、Render 给公开
demo 演示。README 中"key 在目标机器上的安全配置方式"这一要求，迫使我为每种
分发形态单独写清了凭据设置步骤——Docker 用环境变量（需显式 opt-in）、PyPI
用 `testforge credentials set`、Render 完全不需要。

如果重做，我会在项目初期就搭建好 CI build + PyPI 发布 pipeline，而不是到
最后 3 个 task 才集中处理分发。分发的"最后一公里"问题（用户从零安装到看到
第一个 demo 的时间）比预想的更耗时。

---

## 八、如果重做会改变什么

1. **先做 mock-LLM 环路，再补具体模块**。本项目按"领域模型 → 持久化 → 治理
   → 审批 → LLM → 解析 → 反馈 → …"的顺序推进，导致 mock-LLM 可运行的完整
   闭环到 Task 12 才出现。如果重来，我会先做一个"骨架环路"（mock LLM + 最小
   工具分发 + 硬编码反馈），跑通后逐步替换每个模块。这样从第 3 个 task 开始
   就有可演示的产物，而不是等到第 12 个。

2. **CI 从第一个 task 就应该配置并运行**。本项目 CI 在 Task 1 就写了，但 lint
   规则、警告过滤器、跨平台路径等问题直到 Task 15+ 才集中解决。如果每个 task
   合并后立即触发 CI 并修复所有红叉，最后阶段就不会积压大量 CI 相关 commit。

3. **Demo 模式应该作为一等公民设计**，而不是事后追加。公开 demo 是让别人理解
   你项目的最快方式，但本项目直到 Task 17 才实现。如果从一开始就维护一个 mock
   LLM + 内存数据库 + fixture 数据的 demo 模式，每完成一个新功能就能立即在
   demo 中展示。

4. **task brief 的质量应该被评审**，而不仅仅是 task 产出的代码。如果每个 task
   开始前花 5 分钟检查 brief 是否包含：精确文件路径、接口签名、验证命令、
   负面约束，后续的 subagent 偏离会大幅减少。

---

## 九、对 Superpowers 方法论的批判

Superpowers 的核心理念——"流程脚手架守住纪律，让工程师聚焦决策"——在 TestForge
项目中既有成立的证据，也有失效的场景。

**成立的假设：** 对于结构清晰、有明确正确/错误标准的工程任务（如状态机转换、
质量门槛计算、凭据存储），Superpowers 的 SPEC → PLAN → TDD → Review 流程确实
防止了很多典型的 AI 编程陷阱——AI 跳过测试、AI 生成的代码只有"看起来对"的结
构但边界条件缺失、AI 在未经人类确认的情况下做出危险假设。在这些场景中，
Superpowers 是有效的"安全网"。

**不成立的假设：** Superpowers 假设工程师能够写出足够精确的 SPEC。但在项目
早期，我对 TestForge 的理解本身就不完整——我是在构建过程中才逐渐理解什么是
"好的反馈闭环"、审批应该设在哪些节点。Superpowers 的方法论缺少一个"边做边
学、反馈到 SPEC 的迭代机制"——它倾向于假设 SPEC 在实现开始前就是完备的。实
践中，我的 SPEC 在 Task 1-5 阶段修订了多次，但这些修订来自 subagent 的报告
和我对具体实现的观察，而不是 Superpowers 流程本身的某个环节。

另一个局限是：**Superpowers 对"探索性编程"不够友好**。WebUI 的 HTML 布局、
demo 场景的叙事设计、README 的措辞——这些任务不适合 TDD 也不适合严格 SPEC，
它们的质量取决于迭代试错而非前置规约。在这些场景中，Superpowers 的流程显得
过于笨重，强行套用反而降低效率。

**最大的启示：** Superpowers 为 AI 协作提供了下限保障——它防止你做出糟糕的
工程决策。但它不能替代一个工程师的核心判断：什么是正确的产品方向、哪个维度
值得深入、什么时机应该偏离流程。这门课最想教的东西——"当 LLM 能完成大部分编
码工作时，工程师的真正价值在哪里"——我的答案是：**在混沌中建立秩序的能力**。
LLM 可以在给定清晰规约后高效执行，但把模糊需求转化为清晰规约、判读规约在实
现中暴露的缺陷、在多个可行方案中做出取舍——这些仍然需要人的判断。Superpowers
让这些判断变得更可见、更可追溯，但它不是判断的替代品。

