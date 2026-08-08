# TestForge 规约过程记录

> 当前记录范围：Superpowers brainstorming、设计与计划批准、Claude Code 陌生智能体冷启动、全部 19 个任务实现与评审过程。项目代码已完成，`297 passed, 3 skipped`。

## 1. Brainstorming 起点

项目最初路线图推荐 SafeFix（测试失败自动修复）。用户要求查看更多选题后，比较了十二类 Coding Agent Harness，最终选择 TestForge（测试生成智能体）。随后按一次一个问题的方式明确范围、工具、反馈、安全、记忆、凭据、分发和界面。

## 2. 关键迭代

### 迭代一：从“生成测试”收敛为可评价的 Python 单元测试闭环

- **智能体问题**：第一版支持何种技术栈，目标由谁选择，生成何种测试？
- **用户决定**：Python + pytest；用户指定单个文件或模块；只生成纯单元测试。
- **设计变化**：放弃语言无关和全仓库扫描，反馈工具固定为 pytest、coverage.py 与 mutmut。范围收敛后，客观评价和确定性测试更可行。

### 迭代二：从“测试能通过”提升为变异测试驱动的质量门槛

- **智能体问题**：成功采用绝对门槛、相对提升还是预算内尽力优化？
- **用户决定**：相对提升，并选择平衡默认值。
- **设计变化**：全部测试必须通过且指标不得下降；存在存活变异时至少新增杀死 1 个并提高 5 个百分点；无法产生有效变异时，分支覆盖率提高 5 个百分点或达到 90%。反馈闭环成为主要贡献。

### 迭代三：从自动修改转向 Human-Owned 的双审批

- **智能体问题**：是否允许修改生产代码，以及达标测试如何写回？
- **用户决定**：生产代码默认禁止，必要的最小可测试性重构须人工批准；达标测试展示 diff，批准后写回。
- **设计变化**：增加 `AWAITING_REFACTOR_APPROVAL` 与 `AWAITING_APPLY_APPROVAL`，批准绑定具体补丁哈希，真实仓库写回前复核文件哈希。

### 迭代四：处理生成代码执行与公网 WebUI的安全冲突

- **智能体问题**：真实测试在哪里执行，公网 WebUI是否运行用户项目？
- **用户决定**：真实任务在本地临时 Docker 沙箱执行；公网 WebUI只运行内置示例与 mock LLM。
- **设计变化**：Docker 默认禁网、非 root、资源受限且不挂载敏感资源。公网不接受源码、仓库 URL 或用户 API Key，从设计上移除远程任意代码执行面。

### 迭代五：明确记忆和 LLM 适配边界

- **用户疑问**：作业是否禁止 RAG？
- **处理结论**：要求不禁止向量库，但不允许用框架内置 memory 代替自研机制。用户选择项目级结构化记忆，不使用 RAG；LLM 采用供应商无关接口、OpenAI 首个适配器与 mock LLM。
- **设计变化**：记忆只保存配置、历史基线、策略、失败原因和审批决定，不复制完整源码或凭据。

## 3. AI 建议与人工决定

用户采纳了以下建议：Python + pytest、用户指定目标、纯单元测试、领域专用工具、项目级结构化记忆、状态机单任务模型、Docker 沙箱、反馈闭环为主、CLI + 轻量 WebUI、PyPI + Docker 分发。

用户没有把 AI 输出直接当作最终规约，而是逐节确认了总体架构、状态机、核心接口、安全治理、反馈门槛、数据模型、界面部署、错误处理与技术选型。最终设计在用户明确回复“批准设计”后才写入文件。

## 4. 对 brainstorming 的阶段性反思

做得好的地方：一次一个问题有效控制了范围；将“测试数量”转化为覆盖率与变异测试的可验证目标；提前发现公网 WebUI执行陌生 Python 代码的高风险边界；通过双审批体现 Human-Owned。

不足之处：连续选择题容易使用户倾向默认推荐；质量门槛仍需在 fixture 项目与冷启动试运行中验证其现实性；CI 平台和线上 WebUI要求在课程文件中存在冲突，仍需教师确认。

## 5. 冷启动验证阶段说明

用户在全新的 Claude Code 会话与独立目录 `D:\AI4SE-2` 中执行冷启动；会话记录的实际模型标识为 `deepseek-v4-pro`，与主开发 Codex 类型不同。用户只向陌生智能体提供 `SPEC.md` 与 `PLAN.md`。智能体选择 Task 1，并遵守“不确定就暂停”的要求；在写入实现代码和执行 RED 前发现 Python 版本、Git 初始化与虚拟环境规则没有写清，因此停止并提交阻塞报告。该暂停是预期的规约验证行为，不是实现失败。

## 6. Writing-plans 自检修订

实现计划自检发现，真实仓库在网络关闭的 Docker 沙箱中运行前必须先解决项目依赖安装问题。原设计只规定“运行阶段禁网”，没有说明依赖如何进入沙箱。规约据此补充：用户确认仓库可信后，在 `testforge init` 阶段使用固定多阶段 Dockerfile 构建本地项目运行镜像；构建阶段可以获取依赖并执行项目构建后端，最终镜像只保留虚拟环境，不复制源码、不自动推送；候选测试执行阶段继续严格禁网。该修订将在 PLAN 书面审阅门槛中由用户再次确认。

## 7. Claude Code 冷启动第一轮

### 7.1 暂停点与问题

- 冷启动环境只有 Python 3.11.0，而 SPEC 与 PLAN 写成 Python 3.12+，且没有说明能否降级；因此 Task 1 的 `requires-python` 会阻止安装。
- 独立目录尚未初始化 Git，而 PLAN 要求 Task 1 独立提交；文档没有说明分支名和缺少提交身份时的处理方式。
- PLAN 直接从 `pip install -e` 开始，没有明确要求创建项目内 `.venv`，也没有解释 Windows 上 `python`、`py` 和虚拟环境解释器的优先级。
- 智能体还提出 `/` 路径、`.gitignore` 写法和 pytest `tmp_path` 在 Windows 上的兼容性疑问。

### 7.2 技术核验

- 报告中“`match` 可能是 Python 3.12 语法”的推断不成立：结构模式匹配从 Python 3.10 起可用；本计划实际使用的 `enum.StrEnum` 从 Python 3.11 起可用。因此 3.11 是有依据的最低版本，原 3.12 门槛没有必要。
- Git 和虚拟环境问题属于真实规约缺口，因为一个只获得 SPEC 与 PLAN 的实现者无法知道是否被授权初始化仓库、如何提交，或应使用哪个解释器。
- Git、`.gitignore` 和文档中的 `/` 是跨平台约定；运行时路径由 `pathlib.Path` 处理。pytest 官方支持 Windows 上的 `tmp_path`，在没有实际失败证据前不增加特殊规避逻辑。

### 7.3 规约与计划修订

- `SPEC.md`：最低版本由 Python 3.12+ 改为 Python 3.11+；明确 `.venv`、跨平台命令和路径规则；发布容器仍固定 Python 3.12。
- `PLAN.md`：新增执行环境引导；给出 Windows/POSIX 的虚拟环境与解释器选择命令；允许一次性冷启动目录初始化为 `main`；只在缺少身份时使用仓库本地的保留域名验证身份，禁止修改全局 Git 配置。
- `PLAN.md` Task 1：`requires-python` 改为 `>=3.11`，安装与测试明确使用 `.venv` 解释器；CI 以 3.11/3.12 覆盖最低版本和发布版本。
- 冷启动门槛补充：这次正确暂停构成第一轮证据，但须经人工批准修订后由同一隔离智能体继续 Task 1，并回传 RED/GREEN、文件列表、diff 与 commit hash，才算完成冷启动。

### 7.4 产出差距与当前状态

第一轮暂停时，陌生智能体尚未生成代码、RED/GREEN 输出或 commit，因为它在首个不确定点按指示停止。用户随后将修订后的 SPEC/PLAN 提供给同一隔离会话，Claude Code 继续并完成 Task 1。冷启动代码只存在于 `D:\AI4SE-2`，没有合入正式仓库。

### 7.5 Task 1 复跑证据

- **环境**：Python 3.11.0；虚拟环境 `D:\AI4SE-2\.venv`；使用 `.venv/Scripts/python.exe`；可编辑安装最终成功。
- **RED**：运行 `.venv/Scripts/python.exe -m pytest tests/unit/test_config.py -v`，得到 `ModuleNotFoundError: No module named 'testforge.config'`，共 1 个收集错误。
- **GREEN**：实现最小配置模型后运行同一命令，`test_project_config_has_spec_defaults` 与 3 个参数化边界用例全部通过，共 `4 passed`。主 Codex 随后独立复验，Python 3.11.0、pytest 8.4.2 下再次得到 `4 passed in 0.22s`。
- **提交**：`6d225f80731d98b67c531c314e3e7e1b953aa946`，消息为 `build: add validated project configuration`；包含 `.gitignore`、`pyproject.toml`、`src/testforge/__init__.py`、`src/testforge/config.py` 和 `tests/unit/test_config.py`，共 5 个文件、92 行新增。
- **隔离状态**：Claude 报告仅 `SPEC.md` 与 `PLAN.md` 未跟踪，因为它们是冷启动输入而非 Task 1 产物。主 Codex 的受限 Git 环境还显示 `.claude/`，原因是无法读取用户级 Git ignore；该目录仅含 Claude 本地权限设置，不在提交中。

### 7.6 新发现的计划缺口

1. 原 PLAN 的 Hatch 配置在分发名 `testforge-harness` 与 `src/testforge` 包名不完全相同时无法自动推断 wheel 内容，安装报错 `Unable to determine which files to ship inside the wheel`。PLAN Task 1 已补充 `[tool.hatch.build.targets.wheel] packages = ["src/testforge"]`。
2. Windows 冷启动环境的用户级 pytest 临时目录 `C:\Users\34021\AppData\Local\Temp\pytest-of-34021` 可复现 `PermissionError: [WinError 5]`。PLAN 与 SPEC 已明确使用项目内 `.pytest_tmp/`，并加入 `.gitignore`；任务保持顺序执行，避免共享 basetemp。
3. Git 的 LF→CRLF 提示来自 Windows `core.autocrlf`，没有改变测试语义，不作为阻塞。

### 7.7 冷启动结论

陌生智能体在第一轮准确暴露环境前置条件缺口，修订后能够仅依靠 SPEC/PLAN 完成 Task 1，并产生符合 TDD 的 RED、GREEN、diff 与独立提交。冷启动的技术验证达到门槛。用户随后明确回复“批准最终冷启动修订并进入正式实现”，批准了本轮 Python、Git、虚拟环境、Hatch 和 pytest 临时目录修订，并授权开始正式实现。

## 8. 冷启动最终人工批准

- **批准原文**：`批准最终冷启动修订并进入正式实现`。
- **批准范围**：Python 3.11 最低版本、`.venv` 解释器规则、冷启动 Git 初始化与本地身份规则、Hatch wheel 包映射、项目内 pytest basetemp，以及 Task 1 的 RED/GREEN/diff/commit 证据。
- **所有权边界**：`D:\AI4SE-2` 的试做代码不直接合入正式仓库；正式实现从批准后的主仓库提交创建隔离 worktree，按每任务新 subagent、TDD 和两阶段评审执行。
- **门槛结论**：陌生智能体冷启动门槛关闭，允许正式实现。

## 9. 正式实现过程

### 9.1 总体执行

冷启动批准后，使用 `using-git-worktrees` 为每个任务创建隔离 worktree 和分支，并按 `subagent-driven-development` 流程每任务分派独立实施智能体（Claude）和独立评审智能体。所有实现遵循严格 TDD（先 RED，再最小 GREEN，再重构）。

### 9.2 契约暂停模式

实现过程中反复出现以下模式：实施智能体在 RED 前识别出 PLAN 中未定义的公共契约（缺少字段、签名、语义），主动暂停等待人工批准。这种"不确定就暂停"的纪律避免了智能体凭空猜测关键数据契约：

| 任务 | 暂停原因 | 人工裁决 |
|---|---|---|
| Task 2 | 共享领域模型无字段定义 | 补齐 8 个最小不可变契约 |
| Task 3 | 仓储方法缺少签名和语义 | 明确附加/事件/不可变历史 |
| Task 4 | 未知动作模型未定义 | 归入 Task 11；Task 4 只做路径/补丁/预算 |
| Task 5 | 时钟、过期、幂等语义缺失 | 注入 Clock，UTC，CAS 决策 |
| Task 6 | GenerationContext/LLMCall 无字段 | 最小不可变字段 + 只读调用历史 |
| Task 7 | 结果字段、超时/不支持输入未定义 | MutationRunOutcome + 安全诊断 |
| Task 8 | 10 个质量/停滞/分类契约缺口 | MODEL_SWITCH_HANDOFF 批准的完整方案 |

### 9.3 评审发现与修复

每个任务均经只读评审智能体验证。关键发现包括：
- Task 2: 公开可变 TRANSITIONS 表可被外部注入（→ MappingProxyType）
- Task 4: 宿主机路径语法跨平台绕过（→ Windows/POSIX 双语法）
- Task 5: 审批非原子、写回复核竞态、非 UTC 时间戳（→ CAS + 协作锁 + UTC）
- Task 7: 零字段、异常图泄露（→ 严格类型 + 诊断脱敏）
- Task 8: 硬编码默认阈值忽略配置（→ 使用运行时 QualityThreshold）
- Task 12: APPLYING_PATCH 处理器缺失导致死锁（→ 补充处理器）

所有 Critical/Important 发现均在 fix round 内解决并通过专项复审。

### 9.4 Tasks 13–19 合并实施

由于余下任务高度内聚（凭据→适配器→CLI→WebUI→Demo→分发→CI），Tasks 13–19 分为三个实施组：
- **组 A** (Tasks 13+14): 凭据存储 + OpenAI 适配器
- **组 B** (Task 15): CLI
- **组 C** (Tasks 16–19): WebUI + Demo + 机制演示 + 分发 + CI + README

每组由单一实施智能体完成，经独立评审后合入。

### 9.5 最终验证

- 全套测试：`297 passed, 3 skipped`（3 个 skip 为已批准的 Windows 符号链接权限问题）
- 机制演示：确定性 JSON 输出，确认 `dangerous_action.blocked=true`，反馈闭环两轮变换（weak assertion → kill arithmetic mutant），`quality_gate.passed=true`
- 凭据扫描：无真实 key 或 secret 泄露
- 分发产物：Dockerfile、.gitlab-ci.yml、.github/workflows/ci.yml、pyproject.toml 入口点

### 9.6 对 Superpowers 流程的观察

- **契约暂停**是流程中最有价值的机制：智能体在不确定处停止并请求裁决，比自行猜测产生更正确的设计。
- **隔离 worktree**有效防止任务间交叉污染，每个任务有独立的 git 历史。
- **TDD 强制**在 AI 协作中是放大器——实施智能体在 SPEC/PLAN 清晰时能高效地走 RED→GREEN 流程。
- **评审发现**的质量与评审智能体获得的上下文量高度相关：仅给 diff 时偏重代码风格；给完整 SPEC+PLAN 时能发现更深层的语义问题。
- 部分实施智能体自发完成了自检修复（如 Task 3 的时区和外键问题），表明 subagent 在明确契约下可表现出一定的工程判断力。
- SDD progress ledger 仅记录到 Task 9，其余依靠 AGENT_LOG 和 git history，过程追溯性在后半段有所下降。
