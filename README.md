<div align="center">

# Memos Helper

**An AI Agent Skill for Managing Memos Note-Taking Application**

**支持文本、图片、音视频、文档等多种内容类型的完整 CRUD 操作**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen.svg)](https://www.python.org/) [![Memos](https://img.shields.io/badge/Memos-API%20v1-blue)](https://usememos.com)

---

## 简介

Memos Helper 是一个 AI Agent Skill，让你可以通过自然语言或 CLI 管理 [Memos](https://usememos.com) 笔记应用。适用于 Claude Code、Cursor、Windsurf 等支持 Skill/MCP 的 AI 工具。

支持完整的 CRUD 操作，以及图片、视频、音频、文档等多种附件类型。

### ✨ 特性

- ✅ **完整 CRUD 操作** - 创建、读取、更新、删除、搜索
- ✅ **多类型附件上传** - 图片/视频/音频/文档，最大 50MB
- ✅ **严格附件上传模式** - 默认确保所有附件成功才创建 Memo
- ✅ **自动清理机制** - 上传失败或创建失败时自动清理已上传附件
- ✅ **指数退避重试** - 自动应对网络波动，智能区分 4xx/5xx 错误
- ✅ **分离超时控制** - 连接超时与读取超时独立配置
- ✅ **零外部依赖** - 仅使用 Python 标准库，开箱即用

### 📦 安装

将本项目克隆到你的 Agent Skills 目录：

```bash
# Claude Code
git clone https://github.com/moewah/memos-helper.git ~/.claude/skills/memos-helper

# Cursor / Windsurf 等
git clone https://github.com/moewah/memos-helper.git ~/.cursor/skills/memos-helper
```

### ⚙️ 配置

#### 1. 获取 Memos Access Token

登录 Memos → **Settings** → **Access Tokens** → **Create new token**

#### 2. 配置环境变量

```bash
# 持久化配置（推荐）
echo 'export MEMOS_SITE_URL="https://your-memos-instance.com"' >> ~/.zshrc
echo 'export MEMOS_ACCESS_TOKEN="your-access-token"' >> ~/.zshrc
source ~/.zshrc
```

### 🚀 使用方式

#### 自然语言指令

在你的 AI Agent 中直接对话：

```
发条 memo 记录今天的会议要点
搜索包含"项目"的笔记
列出最近 10 条笔记
上传这张图片并创建笔记
```

**触发词**：
- 中文：memo, 备忘录, 笔记, 动态, 发条memo, 写个memo
- English: memo, note-taking, create memo, list memos, search memos

#### CLI 工具

```bash
# 创建笔记
python scripts/memos_cli.py create "笔记内容"

# 带附件上传
python scripts/memos_cli.py create "旅行照片" -f ~/photos/photo1.jpg -f ~/photos/photo2.png

# 其他操作
python scripts/memos_cli.py list --page-size 20
python scripts/memos_cli.py search "关键词"
python scripts/memos_cli.py update memos/xxxxx --content "新内容"
python scripts/memos_cli.py delete memos/xxxxx
```

### 📎 附件支持

| 类型 | 格式 | 限制 |
|------|------|------|
| 图片 | JPG, JPEG, PNG, GIF, WebP, SVG | ≤50MB |
| 视频 | MP4, MOV, AVI, WebM | ≤50MB |
| 音频 | MP3, WAV, OGG, M4A | ≤50MB |
| 文档 | PDF, DOC, DOCX, XLS, XLSX, TXT, MD | ≤50MB |

### 📖 CLI 命令参考

```bash
# 创建
python scripts/memos_cli.py create CONTENT [-t TAG] [-f FILE] [-a ATTACHMENT]
                                           [--visibility PRIVATE|PROTECTED|PUBLIC]

# 列表 / 获取 / 更新 / 删除 / 搜索
python scripts/memos_cli.py list [--page-size N]
python scripts/memos_cli.py get memos/xxxxx
python scripts/memos_cli.py update memos/xxxxx [--content TEXT] [--pinned BOOL]
python scripts/memos_cli.py delete memos/xxxxx
python scripts/memos_cli.py search KEYWORD

# Base64 编码（预编码大文件）
python scripts/memos_cli.py encode FILE [--save] [--output-dir DIR]
```

### 🔧 故障排除

| 问题 | 解决方案 |
|------|----------|
| 401 Unauthorized | 检查 `MEMOS_ACCESS_TOKEN` |
| 404 Not Found | 确认笔记 ID 存在 |
| 连接超时 | 检查 `MEMOS_SITE_URL` 和网络 |

### 📚 更多文档

- [SKILL.md](SKILL.md) - 完整 API 文档
- [Memos 官方文档](https://usememos.com/docs)

### 🤝 贡献

欢迎 PR 和 Issue！

如果这个项目对你有帮助，欢迎 ⭐ Star 支持！

### 📄 许可证

[MIT License](LICENSE)

---

**Author**: MoeWah ([moewah.com](https://www.moewah.com/))

