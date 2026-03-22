---
name: memos-helper
description: |
  Manage Memos note-taking application via REST API. Supports CRUD operations with text, images, videos, audio, and documents.

  TRIGGERS (触发词):
  - English: memo, memos, note-taking, create memo, delete memo, update memo, list memos, search memos, upload to memos, memo attachment
  - 中文: memo, memos, 备忘录, 笔记, 动态, 创建memo, 删除memo, 更新memo, 列出memo, 搜索memo, 上传到memos, memo附件, 发条memo, 写个memo, 发个动态

  REQUIRES: MEMOS_SITE_URL and MEMOS_ACCESS_TOKEN environment variables
---

# Memos Helper Skill

Comprehensive CRUD operations for Memos - a self-hosted note-taking application.

**Author**: MoeWah ([moewah.com](https://moewah.com))
**Version**: 3.3.0

## Features

- ✅ 完整 CRUD 操作（创建、读取、更新、删除、搜索）
- ✅ 多类型附件上传（图片/视频/音频/文档）
- ✅ **严格附件上传模式** - 默认确保所有附件上传成功才创建 Memo
- ✅ **自动清理机制** - 上传失败或创建失败时自动清理已上传附件
- ✅ **指数退避重试机制** - 自动应对网络波动
- ✅ **分离超时控制** - 连接超时与读取超时独立配置
- ✅ **智能错误处理** - 4xx 错误不重试，5xx 错误自动重试
- ✅ 零外部依赖 - 仅使用 Python 标准库

## Prerequisites

- Running Memos instance (self-hosted or cloud)
- Personal access token from Memos settings
- Environment variables configured

## Environment Setup

```bash
export MEMOS_SITE_URL="https://your-memos-instance.com"
export MEMOS_ACCESS_TOKEN="your-access-token"
```

## API Overview

- **Base URL**: `{MEMOS_SITE_URL}/api/v1`
- **Authentication**: Bearer Token
- **Format**: JSON

## Operations

### 1. List Memos

Retrieve memos with optional filtering and pagination.

```bash
GET /api/v1/memos?pageSize=10&filter=row_status == "NORMAL"
```

**Parameters**: `pageSize`, `pageToken`, `filter`

### 2. Create Memo

Create a new memo with optional attachments.

```bash
POST /api/v1/memos
```

**Request Body**:
```json
{
  "content": "Memo content...",
  "visibility": "PRIVATE",
  "pinned": false,
  "attachments": [{"name": "attachments/xxxxx"}]
}
```

**Visibility Options**: `PRIVATE` | `PROTECTED` | `PUBLIC`

### 2.1 Upload Attachment

Upload files before creating memo. **Uses Base64 encoding**.

```bash
POST /api/v1/attachments
```

**Request Body**:
```json
{
  "filename": "image.jpg",
  "type": "image/jpeg",
  "content": "base64-encoded-content"
}
```

**Supported Types** (auto-detected from file extension):
- **Images**: JPG, JPEG, PNG, GIF, WebP, SVG (max 50MB)
- **Videos**: MP4, MOV, AVI, WebM (max 50MB)
- **Audio**: MP3, WAV, OGG, M4A (max 50MB)
- **Documents**: PDF, DOC, DOCX, XLS, XLSX, TXT, MD (max 50MB)

**MIME Type Detection**:
The CLI tool automatically detects MIME types based on file extensions.

### 3. Get Memo

```bash
GET /api/v1/memos/{memo_name}
```

### 4. Update Memo

```bash
PATCH /api/v1/memos/{memo_name}?updateMask=content,visibility
```

**Updateable Fields**: `content`, `visibility`, `pinned`

### 5. Delete Memo

Soft delete by default.

```bash
DELETE /api/v1/memos/{memo_name}
```

### 6. Search Memos

```bash
GET /api/v1/memos?filter=content.contains("keyword")
```

**Filter Examples**:
- `content.contains("meeting")` - Content search
- `row_status == "NORMAL"` - Active memos only
- `visibility == "PUBLIC"` - Public memos only

## Response Format

**Success**: JSON memo object

**Error**:
```json
{
  "code": 3,
  "message": "Invalid argument",
  "details": []
}
```

**Memo Object**:
```json
{
  "name": "memos/abc123",
  "state": "NORMAL",
  "content": "Content...",
  "visibility": "PRIVATE",
  "tags": ["work"],
  "pinned": false,
  "attachments": [],
  "createTime": "2024-01-15T10:30:00Z",
  "updateTime": "2024-01-15T10:30:00Z"
}
```

## CLI Tool Reference

**Location**: `{SKILL_DIR}/scripts/memos_cli.py`

> ⚠️ **重要**: 脚本位于本 skill 目录下的 `scripts/memos_cli.py`。调用时请使用 skill 目录的绝对路径，而非相对于当前工作目录的路径。
>
> 例如，如果本 skill 安装在 `/path/to/skills/memos-helper/`，则脚本路径为：
> `/path/to/skills/memos-helper/scripts/memos_cli.py`

### Commands

```bash
# Create memo (pure text)
python {SKILL_DIR}/scripts/memos_cli.py create "Content" [-t tag] [--visibility TYPE] [--pinned]

# Create memo with local files (auto-upload as base64)
python {SKILL_DIR}/scripts/memos_cli.py create "Content" -f /path/to/file.jpg [-f /path/to/file2.png]

# Create memo with pre-encoded base64 files
python {SKILL_DIR}/scripts/memos_cli.py create "Content" -b /path/to/file.jpg.b64

# Create memo with uploaded attachment references
python {SKILL_DIR}/scripts/memos_cli.py create "Content" -a attachments/xxxxx [-a attachments/yyyyy]

# Create memo in lenient mode (allow partial attachment failures)
python {SKILL_DIR}/scripts/memos_cli.py create "Content" -f file1.jpg -f file2.png --no-strict

# Encode file to base64 (standalone)
python {SKILL_DIR}/scripts/memos_cli.py encode /path/to/file.jpg [--save] [--output-dir DIR]

# List memos
python {SKILL_DIR}/scripts/memos_cli.py list [--page-size N]

# Get memo
python {SKILL_DIR}/scripts/memos_cli.py get memos/xxxxx

# Update memo
python {SKILL_DIR}/scripts/memos_cli.py update memos/xxxxx [--content TEXT] [--visibility TYPE] [--pinned true/false]

# Delete memo
python {SKILL_DIR}/scripts/memos_cli.py delete memos/xxxxx

# Search memos
python {SKILL_DIR}/scripts/memos_cli.py search "keyword"
```

### Strict Attachment Mode (严格附件模式)

**默认行为**: 当有附件时，必须所有附件都上传成功才会创建 Memo。如果部分上传失败，会自动清理已上传的附件并中止创建。

```bash
# 严格模式（默认）：所有附件必须上传成功
python scripts/memos_cli.py create "Trip photos" -f ~/trip/1.jpg -f ~/trip/2.jpg

# 宽松模式：允许部分附件失败时仍创建 Memo
python scripts/memos_cli.py create "Trip photos" -f ~/trip/1.jpg -f ~/trip/2.jpg --no-strict
```

**自动清理机制**：
- 附件上传失败时：自动清理已成功上传的附件
- Memo 创建失败时：自动清理所有已上传的附件

### File Upload (-f flag)

The CLI tool **automatically uploads local files using Base64 encoding**:

```bash
# Upload single file
python scripts/memos_cli.py create "My photo" -f ~/photos/IMG_1234.jpg

# Upload multiple files
python scripts/memos_cli.py create "Trip gallery" -f ~/trip/1.jpg -f ~/trip/2.png -f ~/trip/3.gif

# Combined with other options
python scripts/memos_cli.py create "Meeting notes" -f ~/recordings/meeting.mp3 --visibility PUBLIC -t work
```

**Supported file types**: jpg, jpeg, png, gif, webp, svg, mp4, mov, avi, webm, mp3, wav, ogg, m4a, pdf, doc, docx, xls, xlsx, txt, md

**File size limit**: 50MB per file

### Base64 Encoding (`encode` command)

The CLI tool provides a standalone `encode` command for converting files to Base64 format:

```bash
# Encode file and display base64 content
python scripts/memos_cli.py encode /path/to/file.jpg

# Encode and save as .b64 file
python scripts/memos_cli.py encode /path/to/file.jpg --save

# Encode to specific directory
python scripts/memos_cli.py encode /path/to/file.jpg --save --output-dir ~/encoded

# Batch encode multiple files
python scripts/memos_cli.py encode ~/photos/*.jpg --save --output-dir ~/encoded
```

**Use cases**:
- Pre-encode files for later use (avoids re-encoding)
- Handle large files when network is unstable
- Batch process files before uploading

### Content Type Examples

```bash
# Pure text with tags
python scripts/memos_cli.py create "Learning notes" -t study -t python

# Upload local files (auto base64 encode and attach)
python scripts/memos_cli.py create "Trip photos" -f ~/trip/photo1.jpg -f ~/trip/photo2.png --visibility PUBLIC

# Use pre-encoded base64 files
python scripts/memos_cli.py create "Project docs" -b ~/encoded/design.png.b64 -b ~/encoded/chart.jpg.b64

# Reference already uploaded attachments
python scripts/memos_cli.py create "Meeting summary" -a attachments/audio_xxxxx -a attachments/doc_yyyyy -t work --pinned

# Mixed: upload new files + reference existing attachments
python scripts/memos_cli.py create "Project docs" -f ~/new/design.png -a attachments/existing.pdf -t project

# Mixed: pre-encoded + direct upload + existing attachments
python scripts/memos_cli.py create "Comprehensive" -b ~/encoded/chart.b64 -f ~/new/photo.jpg -a attachments/doc_xxx
```

## Error Handling

| Code | Meaning | Solution |
|------|---------|----------|
| 401 | Unauthorized | Check access token |
| 404 | Not Found | Memo doesn't exist |
| 400 | Bad Request | Invalid parameters |
| 500 | Server Error | Retry later |

## Best Practices

1. **Content**: Use Markdown formatting
2. **Tags**: Add for better organization
3. **Visibility**: Choose appropriate level
4. **Pinning**: Pin important memos
5. **Pagination**: Use `nextPageToken` for large collections
6. **Attachments**: 
   - Use `-f` flag to upload local files directly (auto base64 encode)
   - Use `-a` flag to reference already uploaded attachment names
   - Use `-b` flag for pre-encoded base64 files
   - Maximum 50MB per file

---

© 2024 MoeWah ([moewah.com](https://moewah.com))
