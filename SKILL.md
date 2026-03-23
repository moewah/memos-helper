---
name: memos-helper
description: |
  Manage Memos note-taking application via REST API. Supports CRUD operations with text, images, videos, audio, and documents.

  TRIGGERS (触发词):
  - English: memo, memos, note-taking, create memo, delete memo, update memo, list memos, search memos, upload to memos, memo attachment, attachment, upload file
  - 中文: memo, memos, 备忘录, 笔记, 动态, 创建memo, 删除memo, 更新memo, 列出memo, 搜索memo, 上传到memos, memo附件, 发条memo, 写个memo, 发个动态, 附件, 上传文件

  REQUIRES: MEMOS_SITE_URL and MEMOS_ACCESS_TOKEN environment variables
---

# Memos Helper Skill

CRUD operations for Memos - a self-hosted note-taking application.

**Author**: MoeWah ([moewah.com](https://moewah.com))
**Version**: 4.3.0

## Setup

```bash
export MEMOS_SITE_URL="https://your-memos-instance.com"
export MEMOS_ACCESS_TOKEN="your-access-token"
```

## CLI Location

```
{SKILL_DIR}/scripts/memos_cli.py
```

> Use absolute path to skill directory, not relative to current working directory.

## Quick Commands

```bash
# ==================== Memo Commands ====================

# Create (text only)
python {SKILL_DIR}/scripts/memos_cli.py create "Content" [-t tag] [--visibility PRIVATE|PUBLIC|PROTECTED] [--pinned]

# Create (with local files - auto base64 encode)
python {SKILL_DIR}/scripts/memos_cli.py create "Content" -f /path/to/file.jpg [-f /path/to/file2.png]

# Create (with pre-uploaded attachment references)
python {SKILL_DIR}/scripts/memos_cli.py create "Content" -a attachments/xxxxx

# Create (with options)
python {SKILL_DIR}/scripts/memos_cli.py create "Content" --state ARCHIVED --display-time "2024-01-15T10:30:00Z"

# List memos
python {SKILL_DIR}/scripts/memos_cli.py list [--page-size N] [--state STATE] [--filter EXPR] [--show-deleted]

# Search memos
python {SKILL_DIR}/scripts/memos_cli.py search "keyword"

# Get memo
python {SKILL_DIR}/scripts/memos_cli.py get memos/xxxxx

# Update memo
python {SKILL_DIR}/scripts/memos_cli.py update memos/xxxxx [--content TEXT] [--visibility TYPE] [--pinned true/false] [--state STATE]

# Delete memo
python {SKILL_DIR}/scripts/memos_cli.py delete memos/xxxxx

# Delete memo and cleanup associated attachments
python {SKILL_DIR}/scripts/memos_cli.py delete memos/xxxxx --cleanup-attachments

# ==================== Attachment Commands ====================

# List all attachments
python {SKILL_DIR}/scripts/memos_cli.py att-list [--filter EXPR] [--order-by EXPR]

# Get attachment details
python {SKILL_DIR}/scripts/memos_cli.py att-get attachments/xxxxx

# Update attachment
python {SKILL_DIR}/scripts/memos_cli.py att-update attachments/xxxxx --filename "new_name.jpg"

# Delete attachment
python {SKILL_DIR}/scripts/memos_cli.py att-delete attachments/xxxxx [--force]

# Clean up orphaned attachments (memo field is empty)
python {SKILL_DIR}/scripts/memos_cli.py att-cleanup [--force]

# ==================== Memo Attachment Commands ====================

# List memo's attachments
python {SKILL_DIR}/scripts/memos_cli.py memo-att-list memos/xxxxx

# Set memo's attachments (complete replacement)
python {SKILL_DIR}/scripts/memos_cli.py memo-att-set memos/xxxxx -a attachments/aaaa -a attachments/bbbb
```

## Supported File Types

| Type | Extensions | Max Size |
|------|------------|----------|
| Images | jpg, jpeg, png, gif, webp, svg | 50MB |
| Videos | mp4, mov, avi, webm | 50MB |
| Audio | mp3, wav, ogg, m4a | 50MB |
| Documents | pdf, doc, docx, xls, xlsx, txt, md | 50MB |

## Visibility Options

- `PRIVATE` - Only visible to you
- `PROTECTED` - Visible to logged-in users
- `PUBLIC` - Visible to everyone

## Advanced Topics

For API details, response formats, error handling, attachment service API, strict/lenient modes, and base64 encoding, see:

- `references/advanced.md`