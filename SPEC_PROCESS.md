# TestForge 规约过程记录

> 当前记录范围：Superpowers brainstorming、设计与计划批准，以及 Claude Code 陌生智能体冷启动。Task 1 复跑证据与最终人工批准均已完整记录，正式实现已获授权。

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
