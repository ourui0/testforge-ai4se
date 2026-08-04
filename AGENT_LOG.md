# AGENT_LOG

## 2026-08-04 · SPEC-001

- **阶段/任务**：A 类项目选题与设计规约。
- **Superpowers 技能**：`using-superpowers`、`brainstorming`。
- **关键 context**：课程通用要求、A 类 Harness 专属要求、`PROJECT_ROADMAP.md`；设计阶段禁止实现代码。
- **关键过程**：用户从候选列表中选择 TestForge；逐项确认 Python + pytest、单目标模块、纯单元测试、领域专用工具、结构化记忆、OpenAI + mock、钥匙串、Docker 沙箱、双审批、相对质量门槛、CLI + WebUI 和分发方案。
- **人工干预**：用户逐项选择并逐节批准九个设计部分；最终明确回复“批准设计”。
- **产出**：`SPEC.md`、`SPEC_PROCESS.md`、`docs/superpowers/specs/2026-08-04-testforge-harness-design.md`。
- **subagent/commit**：设计阶段未派发 subagent；设计文档提交为 `c106669`。
- **教训**：测试生成项目必须以缺陷发现能力而非“测试能通过”为成功标准；公网演示与任意代码执行必须从架构上隔离。

## 2026-08-04 · PLAN-001

- **阶段/任务**：将获批 SPEC 拆分为 TDD 实现计划。
- **Superpowers 技能**：`writing-plans`。
- **关键 context**：`SPEC.md`、A 类交付要求、每个任务独立 subagent/PR/双阶段评审、实现前陌生智能体冷启动硬门槛。
- **关键过程**：映射 19 个实现任务，逐项写明文件、接口、RED 命令、最小实现、GREEN 命令、提交信息、依赖和可并行组。
- **人工干预**：用户批准书面 SPEC 后触发本阶段；尚未批准 `PLAN.md`。
- **自检修订**：发现原 SPEC 未说明禁网沙箱如何取得项目依赖，补充“可信仓库在 init 阶段构建本地多阶段项目镜像，运行阶段禁网，最终镜像不含源码且不自动推送”的边界。
- **产出**：`PLAN.md`、`docs/superpowers/plans/2026-08-04-testforge-harness.md`，以及对应的 `SPEC.md` / `SPEC_PROCESS.md` 修订。
- **subagent/commit**：计划编写阶段未派发 subagent；计划与规约修订提交为 `cb30a65`。
- **教训**：沙箱的运行时隔离与依赖供应必须同时设计；只规定“禁网运行”不足以让陌生项目可执行。

## 2026-08-04 · PLAN-APPROVAL-001

- **阶段/任务**：实现计划与计划自检引发的 SPEC 修订审批。
- **Superpowers 技能**：`writing-plans`。
- **人工决定**：用户明确回复“批准 PLAN 与 SPEC 修订”。
- **批准范围**：19 个 TDD 实现任务、依赖/并行关系、双阶段评审、冷启动硬门槛，以及可信仓库依赖镜像的新增安全边界。
- **后续门槛**：使用与主开发 Codex 不同类型的全新智能体，仅提供 `SPEC.md` 与 `PLAN.md`，试做 1–2 个任务；完成记录与修订前禁止正式实现。
- **subagent/commit**：未派发 Codex subagent，因为同类型代理不满足课程冷启动要求；本条记录提交后附哈希。
