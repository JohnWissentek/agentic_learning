# Git 提交与 GitHub 推送自动化规范 (Git Push Automation Rule)

本规范为工作区 `agentic_learning` 的 Git 提交与 GitHub 推送准则，必须严格遵循桌面上的自动化规范执行。

---

## 1. 核心指导文件与权威基准

- **执行指导手册**：`~/Desktop/git_push_automation/AI_github_push_guidance.md`
- **设计原理与背景**：`~/Desktop/git_push_automation/README.md`
- 当两份文件有细微差异时，以 `README.md` 为准并向用户说明。

---

## 2. 核心红线与禁令（严禁违反）

1. **绝对禁止直接运行普通 `git push`**：
   - 任何向 GitHub 的推送操作，**只能且必须**使用 `github_push push`（或 `~/.local/bin/github_push push`）。
   - 严禁任何形式的强推（`--force`、`--force-with-lease`、`-f`）。
2. **严禁绕过钩子与篡改元数据**：
   - 严禁使用 `git commit --no-verify` / `-n` 跳过提交钩子。
   - 严禁修改或删除 `.git/hooks/commit-msg`。
   - 严禁在提交说明中手工编写 `Device:`、`Hardware:` 等标记行（全部由钩子自动提取与写入）。
3. **严禁破坏提交历史**：
   - 严禁对已推送的提交执行 `git reset --hard`、`git rebase -i`、`git commit --amend`。
   - 严禁不带 `--rebase` 或 `--ff-only` 的直接 `git pull`（避免产生无意义的 Merge 提交）。
   - 解决冲突时严禁使用 `--ours`/`--theirs`（在 rebase 中含义易造成不可逆代码丢失），必须用白话选项由用户决策后直接写入合并内容。

---

## 3. 开工与修改前检查（附录 A）

在任何会话中第一次修改代码/文档文件前，或用户要求“开工”、“拉取最新”时：
```bash
git fetch origin
git status -sb
```
- 若落后于远端（`behind`），在没有工作区改动时执行 `git pull --ff-only origin main`；
- 若同时有 `ahead` 与 `behind`，提示用户后先备份分支再进行 `git pull --rebase origin main`。

---

## 4. 提交格式要求

提交标题格式必须为：
```text
<类型>[(范围)][!]: <中文摘要>
```
- 类型限定为：`feat`、`fix`、`docs`、`refactor`、`perf`、`test`、`build`、`ci`、`chore`、`style`、`revert`
- 摘要必须使用中文，明确交代“做了什么、为什么”，不超过 50 个汉字，严禁空泛用词（如“更新”、“update”、“fix bug”等）。
- 改动较多时提供条目化正文，分行以 `- ` 开头。

---

## 5. 汇报规范

推送完成或遇到异常停止时，严格按照以下格式汇报：
```text
结果：已推送 / 未推送（原因）
提交：<短哈希> <标题>
设备：<Device 行的内容>
推送到：origin/main
需要你处理：<没有 / 具体事项>
```

---

## 6. 多命名空间（个人与组织）自动探测与切换（对应指导文件 1.4 版第 3 步 4.1 与 7.5 节）

用户拥有两个 GitHub 空间：个人账号（`JohnWissentek`）与公司组织（`Wissentek`）。
- 在检查 `origin` 或推送遇到 `403` / `404`（`not found` 或 `Write access to repository not granted`）时：
  1. 查看当前 `origin` 地址中的命名空间（`JohnWissentek` 或 `Wissentek`）；
  2. 自动探测另一个命名空间（`git ls-remote https://github.com/<另一空间>/<repo>.git HEAD`）；
  3. 若切换后连通成功，自动执行 `git remote set-url origin <新地址>` 并继续执行 `"$GP" push`；
  4. 若两边均无法连通，再停下询问用户。
