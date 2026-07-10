# Contributing to Octop

Thank you for your interest in contributing! Octop is the control-plane application in the [Octop Harness](https://github.com/TencentCloud) ecosystem.

## Getting started

**Prerequisites:** Python 3.11+, Node.js 18+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/TencentCloud/Octop.git octop
cd octop
make install          # backend dev dependencies
make all              # backend lint + typecheck + test (CI ship bar)
```

For frontend work (separate terminal):

```bash
make dev-frontend     # Vite dev server
make lint-frontend
make typecheck-frontend
make check-all        # full stack quality gate
```

## Development workflow

| Command | Description |
|---------|-------------|
| `make install` | Install Python dev dependencies |
| `make all` | Backend lint + typecheck + test |
| `make check-all` | Full stack quality gate |
| `make dev` | Start frontend + backend dev servers |
| `make build` | Build dashboard + Python wheel |
| `make docs-cli` | Regenerate CLI documentation |

## Pull requests

1. Fork the repository and create a feature branch from `main`
2. Add or update tests for behavior changes
3. Run `make all` (backend) or `make check-all` (full stack) before submitting
4. Update `CHANGELOG.md` when user-facing behavior changes
5. Open a PR with a clear description and test plan

See [AGENTS.md](AGENTS.md) for module boundaries and coding conventions.

## Releases

Tag `v<version>` to trigger build, PyPI publish, and GitHub Release.

---

# 贡献指南

感谢你对 Octop 的关注！Octop 是 [Octop Harness](https://github.com/TencentCloud) 生态中的可自托管 AI 助手平台，支持多用户与多 Agent。

## 环境搭建

**前置条件：** Python 3.11+、Node.js 18+、[uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/TencentCloud/Octop.git octop
cd octop
make install
make all              # 后端质量门禁
```

前端开发（另开终端）：

```bash
make dev-frontend
make check-all        # 全栈质量门禁
```

## 提交流程

1. Fork 仓库，从 `main` 创建特性分支
2. 补充测试，运行 `make all` 或 `make check-all`
3. 更新 `CHANGELOG.md`
4. 提交 Pull Request

模块边界与编码规范见 [AGENTS.md](AGENTS.md)。

推送 `v<version>` 标签后自动构建并发布。
