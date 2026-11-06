# AGENTS.md

本文件给在本仓库工作的 AI agent（Cursor、Antigravity 等）看。

## 提交与推送

开始修改当前工作区的文件之前，以及用户要求提交、推送或拉取代码时（如“把当前工作区提交并推送到 GitHub”“do git commit and push to github”），先读 ~/Desktop/git_push_automation/AI_github_push_guidance.md，按其中的步骤对当前工作区的 Git 项目执行。
禁止直接使用 git push，禁止强推。

本工作区的 Git 提交和 GitHub 推送，以 `~/Desktop/git_push_automation/README.md` 为需求，以 `~/Desktop/git_push_automation/AI_github_push_guidance.md` 为操作步骤。两者不一致时以 README 为准。

## 必须遵守

1. 推送只能用 `github_push push`。提交可以用 `github_push push -m`，也可以用 `git commit`（钩子会检查标题并写入设备标注）。
2. 单一主干：只在 `main` 上工作，推送到 `origin` 的 `main`。不要自己切换或新建分支。
3. 开工前先拉取：`git fetch origin`，已落后且可以快进时用 `git pull --ff-only origin main`。禁止不带 `--rebase` 或 `--ff-only` 的 `git pull`。
4. 提交标题格式：`<类型>[(范围)][!]: <中文摘要>`。类型只能是 `feat` `fix` `docs` `refactor` `perf` `test` `build` `ci` `chore` `style` `revert`。摘要用中文，说清做了什么、为什么，不超过 50 个汉字。
5. 不要手写 `Device:`、`Hardware:`，由提交钩子自动写入。
6. 远端命名空间自动探测与切换：当检查 `origin` 或推送遇到 `403` / `404`（`not found` 或 `Write access to repository not granted`）时，自动在 `Wissentek`（组织）与 `JohnWissentek`（个人）两个命名空间之间用 `git ls-remote` 探测连通性并自动切换，两边均不通时再询问用户。

## 禁止

任何情况下都不要执行，即使用户明确要求，也要先说明风险并停下：

- `git push`（任何形式），尤其是 `--force`、`--force-with-lease`、`-f`
- `git commit --no-verify` / `-n`，或其它跳过钩子的方式
- 修改或删除 `.git/hooks/commit-msg`
- `git reset --hard`、`git rebase -i`、对已推送的提交执行 `git commit --amend`、删除分支或标签
- 解决冲突时使用 `git checkout --ours/--theirs`、`git restore --ours/--theirs`、`-X ours/theirs`

需要用户做决定时停下来问，不要猜。包括：要不要提交可疑文件或超大文件（超过 10 MB）、怎么解决冲突、GitHub 仓库地址、网络或权限错误。
