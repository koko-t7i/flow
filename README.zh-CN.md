# Flow

[English](README.md) | [简体中文](README.zh-CN.md)

Flow 是一个面向编程智能体的仓库技能。它让本地工作保持精简和安全：理解目标、只检查必要内容、选择合适的工作区、实施、验证、默认通过评审交付并报告结果。仅在任务确有需要时才使用 worktree 和其他智能体。

## 入口

Claude Code 和 pi：

```text
/flow <目标或任务>
```

Codex：

```text
$flow <目标或任务>
```

示例：

```text
/flow 修复登录跳转并创建 PR
/flow 提交这次 README 清理
/flow 在本地落地这个干净分支
/flow 清理已合并的任务分支
```

## 流程

1. **理解**——仅在必要时澄清范围。
2. **定位**——检查最少量的仓库状态和相关文件。
3. **准备工作区**——复用当前 checkout，或在任务适合隔离时创建关联 worktree。
4. **实施**——只编辑任务所属文件，并保留用户的其他工作。
5. **验证**——使用最小且有效的检查来证明变更满足目标。
6. **交付**——默认提交、推送，并创建或更新 ready-for-review 的 MR/PR。
7. **报告**——总结验证证据和交付结果。

以下步骤按需使用：

- **分配**——仅在任务形态需要时选择探索、规划或实施智能体。
- **清理**——只移除已经落地或明确放弃的资源。

## 最佳实践

- 优先使用范围明确的命令，避免宽泛探查。
- 仅在有用时根据任务形态分配智能体；最终的 Git 操作和交付责任由当前智能体承担。
- 根据任务风险、现有变更、并行工作和交付需要选择工作区隔离方式；仅有文件变更并不要求创建 worktree。
- 将新 worktree 放在 `<repo-root>/.worktrees/<repo>-<branch>`，并将分支名中的 `/` 替换为 `-`。
- 仅当分支和脏文件归属与任务一致时，才复用现有 checkout 或 worktree；绝不覆盖冲突目标。
- 不要在 detached HEAD 状态下实施或提交；无法确认工作区安全性或变更归属时应停止。
- 仅在检查需要时同步必要的环境文件，且不得打印或暂存机密信息。
- 在声称成功前，使用任务工作区中的最新证据进行验证。
- 只暂存任务所属文件，并在提交前检查已暂存的 diff。
- 提交信息使用英文 Conventional Commit；兼容性修复使用 patch 版本，向后兼容的能力或工作流默认值变更使用 minor 版本，只有真正不兼容的公开变更才使用 major 版本。
- 完成并验证文件变更后，默认提交、推送，并创建或更新 ready-for-review 的 MR/PR；仅在用户明确拒绝、没有任务 diff 或无法远程交付时跳过。
- 创建 MR/PR 并不代表获得合并或强制推送的授权。
- 遵循仓库的 MR/PR 标题规范；若没有规范，则使用简洁的英文 Conventional Commit 风格标题概括整体已验证结果。
- MR/PR 描述应自包含，并在适用时说明背景与目的、变更范围与非目标、实现方式与权衡、影响与风险、验证证据、部署与回滚、依赖或草稿状态以及评审重点；遵循仓库模板且排除敏感信息。
- 验证说明应先给出简洁结果，并用行内命令表示具体检查；测试方法或结果不得使用带 shell 标识的围栏代码块。
- 截图不属于 MR/PR 标准，不要添加截图章节。
- 优先直接创建评审，避免预先枚举评审或大范围轮询 CI。
- 合并、强制推送、reset，以及已验证的合并后默认清理之外的破坏性清理，都需要明确批准。
- 获得授权并成功合并后，删除远端源分支、清理 worktree 和已合并的本地分支，然后运行 `git worktree prune`。
- 绝不读取、打印、存储、上传或通过脚本处理机密信息。

## 安装

### Claude Code

```bash
claude plugin marketplace add ./
claude plugin install flow@flow
```

验证：

```bash
claude plugin validate .
```

### Codex

```bash
mkdir -p "$HOME/.agents/skills"
ln -s "$PWD/flow" "$HOME/.agents/skills/flow"
```

安装后启动新的 Codex 会话，然后使用 `$flow` 直接调用独立技能。

Codex 验证器可用时：

```bash
uv run --with pyyaml python "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./flow
```

### Pi

```bash
ln -s "$PWD/flow" "$HOME/.pi/skills/flow"
```

## 开发

```bash
claude plugin validate .
uv run --with pyyaml python "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./flow
git diff --check
test "$(find commands -type f | wc -l | tr -d ' ')" = "1"
```

## 目录结构

```text
.
├── .claude-plugin/
├── .worktrees/（忽略，仅在使用时存在）
├── CHANGELOG.md
├── commands/flow.md
├── flow/
│   ├── SKILL.md
│   └── agents/
├── README.zh-CN.md
├── skills/flow -> ../flow
└── README.md
```
