# Advanced Topics

Detailed documentation for advanced use cases.

## API Overview

- **Base URL**: `{MEMOS_SITE_URL}/api/v1`
- **Authentication**: Bearer Token
- **Format**: JSON

## Memo API Endpoints

### List Memos

```bash
GET /api/v1/memos?pageSize=10&filter=row_status == "NORMAL"
```

**Parameters**:
- `pageSize` - Number of memos per page
- `pageToken` - Pagination token
- `filter` - Filter expression
- `state` - Filter by state (NORMAL, ARCHIVED)
- `orderBy` - Sort order (e.g., `create_time desc`)
- `showDeleted` - Include deleted memos

### Create Memo

```bash
POST /api/v1/memos
```

**Request Body**:
```json
{
  "content": "Memo content...",
  "visibility": "PRIVATE",
  "pinned": false,
  "state": "NORMAL",
  "displayTime": "2024-01-15T10:30:00Z",
  "createTime": "2024-01-15T10:30:00Z",
  "attachments": [{"name": "attachments/xxxxx"}]
}
```

> Note: `createTime` and `displayTime` can only be set during creation, not during updates.

### Get / Update / Delete Memo

```bash
GET /api/v1/memos/{memo_name}
PATCH /api/v1/memos/{memo_name}?updateMask=content,visibility
DELETE /api/v1/memos/{memo_name}
```

**Updatable Fields**: `content`, `visibility`, `pinned`, `state`

### Search Memos

```bash
GET /api/v1/memos?filter=content.contains("keyword")
```

**Filter Examples**:
- `content.contains("meeting")` - Content search
- `row_status == "NORMAL"` - Active memos only
- `visibility == "PUBLIC"` - Public memos only

## Attachment Service API

Memos provides complete attachment management API with independent CRUD operations.

### Create Attachment

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

**Query Parameters**:
- `attachmentId` (optional): Custom attachment ID

### List Attachments

```bash
GET /api/v1/attachments?pageSize=50&filter=mime_type=="image/png"
```

**Parameters**:
- `pageSize`: Max results (default 50, max 1000)
- `pageToken`: Pagination token
- `filter`: Filter expression
- `orderBy`: Sort order (e.g., `create_time desc`)

**Filter Examples**:
- `mime_type=="image/png"` - Filter by MIME type
- `filename.contains("test")` - Filename contains "test"
- `create_time > "2024-01-01"` - Created after date

### Get / Update / Delete Attachment

```bash
GET /api/v1/attachments/{attachment_id}
PATCH /api/v1/attachments/{attachment_id}?updateMask=filename,memo
DELETE /api/v1/attachments/{attachment_id}
```

**Updatable Fields**: `filename`, `content`, `externalLink`, `type`, `memo`

## Response Format

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

**Attachment Object**:
```json
{
  "name": "attachments/abc123",
  "createTime": "2024-01-15T10:30:00Z",
  "filename": "image.jpg",
  "type": "image/jpeg",
  "size": "102400",
  "externalLink": "",
  "memo": "memos/xyz789"
}
```

**Error Response**:
```json
{
  "code": 3,
  "message": "Invalid argument",
  "details": []
}
```

## Error Handling

| Code | Meaning | Solution |
|------|---------|----------|
| 401 | Unauthorized | Check access token |
| 404 | Not Found | Resource doesn't exist |
| 400 | Bad Request | Invalid parameters |
| 500 | Server Error | Retry later |

## Strict vs Lenient Attachment Mode

**Default (Strict Mode)**: All attachments must upload successfully before creating memo. If any upload fails, automatically cleans up successfully uploaded attachments and aborts creation.

```bash
# Strict mode (default)
python scripts/memos_cli.py create "Trip photos" -f ~/trip/1.jpg -f ~/trip/2.jpg

# Lenient mode - create memo even if some attachments fail
python scripts/memos_cli.py create "Trip photos" -f ~/trip/1.jpg -f ~/trip/2.jpg --no-strict
```

**Auto-cleanup**:
- On upload failure: cleans up successfully uploaded attachments
- On memo creation failure: cleans up all uploaded attachments

## Base64 Encoding (Standalone)

```bash
# Encode and display
python scripts/memos_cli.py encode /path/to/file.jpg

# Encode and save as .b64 file
python scripts/memos_cli.py encode /path/to/file.jpg --save

# Encode to specific directory
python scripts/memos_cli.py encode /path/to/file.jpg --save --output-dir ~/encoded

# Batch encode
python scripts/memos_cli.py encode ~/photos/*.jpg --save --output-dir ~/encoded
```

**Use cases**:
- Pre-encode files for later use
- Handle large files when network is unstable
- Batch process before uploading

## Mixed Attachment Patterns

```bash
# Upload new files + reference existing attachments
python scripts/memos_cli.py create "Project docs" -f ~/new/design.png -a attachments/existing.pdf

# Pre-encoded + direct upload + existing attachments
python scripts/memos_cli.py create "Comprehensive" -b ~/encoded/chart.b64 -f ~/new/photo.jpg -a attachments/doc_xxx

# Use pre-encoded base64 files
python scripts/memos_cli.py create "Project docs" -b ~/encoded/design.png.b64 -b ~/encoded/chart.jpg.b64
```

## Attachment Management Examples

```bash
# Filter by MIME type
python scripts/memos_cli.py att-list --filter 'mime_type=="image/png"'

# Filter by filename
python scripts/memos_cli.py att-list --filter 'filename.contains("screenshot")'

# Sort by creation time (newest first)
python scripts/memos_cli.py att-list --order-by "create_time desc"

# Update attachment content (replace with new file)
python scripts/memos_cli.py att-update attachments/abc123 --file ~/new_photo.jpg

# Link attachment to a memo
python scripts/memos_cli.py att-update attachments/abc123 --memo memos/xyz789
```

## Retry Mechanism

The CLI tool includes:
- **Exponential backoff retry** - handles network fluctuations
- **Separate timeout controls** - connection and read timeouts configured independently
- **Smart error handling** - 4xx errors don't retry, 5xx errors auto-retry

**命令行参数**：`--retry` 在 create 命令中使用，失败时自动重试一次
```bash
python scripts/memos_cli.py create "重要内容" -f photo.jpg --retry
```

## Best Practices

1. **Content**: Use Markdown formatting
2. **Tags**: Add for better organization
3. **Visibility**: Choose appropriate level
4. **Pinning**: Pin important memos
5. **Pagination**: Use `nextPageToken` for large collections
6. **Attachments**:
   - Use `-f` for local files (auto base64 encode)
   - Use `-a` for pre-uploaded attachment names
   - Use `-b` for pre-encoded base64 files
   - Maximum 50MB per file