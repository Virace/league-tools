# 维护阶段开发、切换与发布流程（test -> package）

本文用于当前维护阶段的固定流程，采用双分支模型：

- `test`：开发与回归分支
- `package`：发布分支

`main`、`release/*` 等分支可保留历史用途，但不再作为日常流程必经路径。

## 1. 流程总览

1. 在 `test` 完成开发、回归测试、版本号确认
2. 将 `test` 合并到 `package`
3. 基于 `package` 创建 `tag + GitHub Release`
4. GitHub Actions 自动校验并通过 Trusted Publishing 上传到 PyPI

## 2. 分支职责

- `test`
  - 日常开发、缺陷修复、测试验证
  - 允许频繁提交
- `package`
  - 仅接收待发布代码
  - 不直接做功能开发
  - 仅在发布前由 `test` 合并而来

## 3. 日常开发流程（test）

### 3.1 切入分支与同步

```bash
git switch test
git pull --ff-only origin test
```

### 3.2 开发与验证

```bash
uv run pytest -q
```

涉及真实样本链路时，按 `docs/development_testing.md` 执行完整链路测试。

### 3.3 提交

```bash
git add <files>
git commit -m "fix(scope): 修复xxxx"
git push origin test
```

## 4. 分支切换规范

切换前固定检查：

```bash
git status --short
git diff --cached --name-only
```

切换与同步：

```bash
git switch test
git switch package
git pull --ff-only origin <branch>
```

## 5. 标准发布流程（package）

### 5.1 发布前检查（在 test）

```bash
git switch test
git pull --ff-only origin test
git status --short
git diff --cached --name-only
git fetch --all --prune
uv run pytest -q
```

检查版本号（必须是正式要发布的版本）：

```bash
rg -n '^version = ' pyproject.toml
```

### 5.2 合并 test 到 package

优先走常规合并：

```bash
git switch package
git pull --ff-only origin package
git merge --no-ff test -m "merge(release): test -> package"
git push origin package
```

若出现分支异常（历史分叉、冲突复杂、无法快速确认）：

1. 先备份当前远端 `package`
2. 再强制将 `test` 覆盖到 `package`

```bash
git fetch --all --prune
OLD_PACKAGE_SHA="$(git rev-parse --short origin/package)"

# 1) 备份旧 package
git branch "backup/package-pre-${OLD_PACKAGE_SHA}" origin/package
git push origin "backup/package-pre-${OLD_PACKAGE_SHA}"

# 2) 强制覆盖 package（以 test 为准）
git push --force-with-lease=package:${OLD_PACKAGE_SHA} origin test:package
```

### 5.3 在 package 创建 tag 并发布 GitHub Release

建议 tag 使用 `vX.Y.Z`，并要求与 `pyproject.toml` 的 `version` 一致。

```bash
git switch package
git pull --ff-only origin package
git tag -a vX.Y.Z -m "release: vX.Y.Z"
git push origin vX.Y.Z
```

然后在 GitHub UI 基于该 tag 创建并发布 Release（`published`）。

### 5.4 自动发布（GitHub Actions）

工作流文件：

- `.github/workflows/python-publish.yml`

触发条件：

- `release` 事件类型为 `published`

自动校验：

1. `release.target_commitish` 必须是 `package`
2. `pyproject.toml` 中 `version` 必须与 tag（去掉前缀 `v` 后）完全一致

通过后动作：

1. 在 CI 中构建 `dist/*`（`python -m build`）
2. 通过 Trusted Publishing 上传到 PyPI

> 说明：本地与 CI 均使用原生 `uv`。

## 6. Trusted Publishing 配置清单（PyPI 侧）

在 PyPI 项目 `league-tools` 的 Trusted Publisher 中需要配置：

1. PyPI 项目名：`league-tools`
2. GitHub 仓库：`<owner>/<repo>`
3. Workflow 文件名：`python-publish.yml`
4. Environment 名称：`pypi`

配置完成后，本仓库无需保存 `PYPI_API_TOKEN`。

## 7. 常见失败与处理

- 失败：`release.target_commitish` 不是 `package`
  - 处理：重新从 `package` 创建/发布 Release
- 失败：版本不一致
  - 处理：对齐 `pyproject.toml` 的 `version` 与 tag，再重新发布
- 失败：PyPI trusted publishing 拒绝
  - 处理：核对 PyPI 侧 Trusted Publisher 的仓库、workflow、environment 配置

## 8. 常用命令速查

```bash
# 查看版本
rg -n '^version = ' pyproject.toml

# 同步远端
git fetch --all --prune

# 最小回归
uv run pytest -q

# 合并发布
git switch package
git pull --ff-only origin package
git merge --no-ff test -m "merge(release): test -> package"
git push origin package
```
