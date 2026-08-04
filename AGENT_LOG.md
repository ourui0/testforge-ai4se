# AGENT_LOG

## 2026-08-04 · SPEC-001

- **阶段/任务**：A 类项目选题与设计规约。
- **Superpowers 技能**：`using-superpowers`、`brainstorming`。
- **关键 context**：课程通用要求、A 类 Harness 专属要求、`PROJECT_ROADMAP.md`；设计阶段禁止实现代码。
- **关键过程**：用户从候选列表中选择 TestForge；逐项确认 Python + pytest、单目标模块、纯单元测试、领域专用工具、结构化记忆、OpenAI + mock、钥匙串、Docker 沙箱、双审批、相对质量门槛、CLI + WebUI 和分发方案。
- **人工干预**：用户逐项选择并逐节批准九个设计部分；最终明确回复“批准设计”。
- **产出**：`SPEC.md`、`SPEC_PROCESS.md`、`docs/superpowers/specs/2026-08-04-testforge-harness-design.md`。
- **subagent/commit**：设计阶段未派发 subagent；commit 在文档自检通过后记录。
- **教训**：测试生成项目必须以缺陷发现能力而非“测试能通过”为成功标准；公网演示与任意代码执行必须从架构上隔离。
