#!/usr/bin/env python3
"""
Memos CLI - 完整版

支持功能:
- 纯文本内容 (支持 Markdown 和标签)
- 本地文件自动上传 (图片/视频/音频/文档)
- 完整的 Memo CRUD 操作
- 完整的附件 CRUD 操作 (创建/列表/获取/更新/删除)
- 搜索功能
- 网络波动自适应重试

环境变量:
- MEMOS_SITE_URL: Memos 实例 URL
- MEMOS_ACCESS_TOKEN: 访问令牌

作者: MoeWah (moewah.com)
版本: 4.2.0
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import ssl
import base64
import mimetypes
import socket
import time
import random
from urllib.parse import urlencode, quote

# ============================================================================
# 网络配置常量
# ============================================================================
DEFAULT_CONNECT_TIMEOUT = 10      # 连接超时（秒）
DEFAULT_READ_TIMEOUT = 60         # 读取超时（秒）
DEFAULT_MAX_RETRIES = 3           # 最大重试次数
DEFAULT_BASE_RETRY_DELAY = 1      # 基础重试延迟（秒）
DEFAULT_MAX_RETRY_DELAY = 30      # 最大重试延迟（秒）
DEFAULT_JITTER = 0.5              # 抖动因子（防止重试风暴）
DEFAULT_UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024  # 分块上传大小（5MB）


# 文件类型映射（扩展名 -> MIME类型）
MIME_TYPES = {
    # 图片
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    # 视频
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    # 音频
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    # 文档
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def get_mime_type(filepath):
    """根据文件扩展名获取MIME类型"""
    ext = os.path.splitext(filepath)[1].lower()
    # 优先使用自定义映射
    if ext in MIME_TYPES:
        return MIME_TYPES[ext]
    # 回退到系统检测
    mime_type, _ = mimetypes.guess_type(filepath)
    return mime_type or "application/octet-stream"


def is_supported_file(filepath):
    """检查文件类型是否受支持"""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in MIME_TYPES


def encode_file_to_base64(filepath):
    """将文件编码为 Base64 字符串

    Args:
        filepath: 文件路径

    Returns:
        dict: 包含 filename, mime_type, base64_content, size 的字典
              失败返回 None
    """
    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}", file=sys.stderr)
        return None

    filename = os.path.basename(filepath)
    mime_type = get_mime_type(filepath)
    file_size = os.path.getsize(filepath)

    # 检查文件大小（限制50MB）
    if file_size > 50 * 1024 * 1024:
        print(
            f"❌ 文件过大 ({file_size / 1024 / 1024:.1f}MB > 50MB): {filename}",
            file=sys.stderr,
        )
        return None

    try:
        with open(filepath, "rb") as f:
            content = f.read()
        base64_content = base64.b64encode(content).decode("utf-8")

        return {
            "filename": filename,
            "mime_type": mime_type,
            "base64_content": base64_content,
            "size": file_size,
            "size_human": f"{file_size / 1024:.1f}KB"
            if file_size < 1024 * 1024
            else f"{file_size / 1024 / 1024:.1f}MB",
        }
    except Exception as e:
        print(f"❌ 读取文件失败 {filename}: {e}", file=sys.stderr)
        return None


def decode_base64_to_file(base64_content, output_path):
    """将 Base64 字符串解码为文件

    Args:
        base64_content: Base64 编码的字符串
        output_path: 输出文件路径

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        content = base64.b64decode(base64_content)
        with open(output_path, "wb") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"❌ 解码失败: {e}", file=sys.stderr)
        return False


def save_base64_to_file(filepath, output_dir=None):
    """将文件编码并保存为 .b64 文本文件

    Args:
        filepath: 源文件路径
        output_dir: 输出目录，默认为源文件所在目录

    Returns:
        str: 生成的 .b64 文件路径，失败返回 None
    """
    result = encode_file_to_base64(filepath)
    if not result:
        return None

    # 确定输出路径
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.basename(filepath)
        output_path = os.path.join(output_dir, f"{base_name}.b64")
    else:
        output_path = f"{filepath}.b64"

    # 生成元数据
    metadata = {
        "filename": result["filename"],
        "mime_type": result["mime_type"],
        "size": result["size"],
        "size_human": result["size_human"],
        "encoded_at": "__timestamp__",
    }

    # 保存为 JSON 格式（包含元数据和 base64 内容）
    data = {"metadata": metadata, "content": result["base64_content"]}

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"✅ 已保存: {output_path}")
        print(
            f"   文件: {result['filename']} ({result['mime_type']}, {result['size_human']})"
        )
        return output_path
    except Exception as e:
        print(f"❌ 保存失败: {e}", file=sys.stderr)
        return None


def load_base64_from_file(b64_filepath):
    """从 .b64 文件加载编码内容

    Args:
        b64_filepath: .b64 文件路径

    Returns:
        dict: 包含 filename, mime_type, base64_content 的字典
              失败返回 None
    """
    if not os.path.exists(b64_filepath):
        print(f"❌ 文件不存在: {b64_filepath}", file=sys.stderr)
        return None

    try:
        with open(b64_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        metadata = data.get("metadata", {})
        return {
            "filename": metadata.get("filename"),
            "mime_type": metadata.get("mime_type"),
            "base64_content": data.get("content"),
            "size": metadata.get("size"),
            "size_human": metadata.get("size_human"),
        }
    except json.JSONDecodeError:
        # 尝试作为纯 base64 文本读取
        try:
            with open(b64_filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            return {
                "filename": os.path.basename(b64_filepath).replace(".b64", ""),
                "mime_type": "application/octet-stream",
                "base64_content": content,
            }
        except Exception as e:
            print(f"❌ 读取失败: {e}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"❌ 读取失败: {e}", file=sys.stderr)
        return None


def get_env_vars():
    """获取环境变量"""
    site_url = os.environ.get("MEMOS_SITE_URL")
    token = os.environ.get("MEMOS_ACCESS_TOKEN")

    if not site_url:
        print("错误: 未设置 MEMOS_SITE_URL 环境变量", file=sys.stderr)
        print(
            '请设置: export MEMOS_SITE_URL="https://your-memos-instance.com"',
            file=sys.stderr,
        )
        sys.exit(1)

    if not token:
        print("错误: 未设置 MEMOS_ACCESS_TOKEN 环境变量", file=sys.stderr)
        print('请设置: export MEMOS_ACCESS_TOKEN="your-access-token"', file=sys.stderr)
        sys.exit(1)

    return site_url.rstrip("/"), token


def check_network_connectivity(site_url, timeout=5):
    """检测网络连通性

    Returns:
        bool: True 表示网络正常，False 表示网络异常
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(site_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()

        return result == 0
    except Exception:
        return False


def calculate_retry_delay(attempt, base_delay=DEFAULT_BASE_RETRY_DELAY, max_delay=DEFAULT_MAX_RETRY_DELAY, jitter=DEFAULT_JITTER):
    """计算指数退避延迟时间（带抖动）

    Args:
        attempt: 当前重试次数（从1开始）
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        jitter: 抖动因子（0-1）

    Returns:
        float: 延迟时间（秒）
    """
    # 指数退避: base_delay * 2^(attempt-1)
    delay = base_delay * (2 ** (attempt - 1))

    # 添加随机抖动，防止重试风暴
    jitter_value = delay * jitter * random.random()
    delay = delay + jitter_value

    # 限制最大延迟
    return min(delay, max_delay)


def make_request(method, url, token, data=None, max_retries=DEFAULT_MAX_RETRIES,
                 connect_timeout=DEFAULT_CONNECT_TIMEOUT, read_timeout=DEFAULT_READ_TIMEOUT):
    """发送 HTTP 请求到 Memos API（带指数退避重试）

    Args:
        method: HTTP 方法
        url: 请求 URL
        token: 访问令牌
        data: 请求体数据
        max_retries: 最大重试次数
        connect_timeout: 连接超时（秒）
        read_timeout: 读取超时（秒）

    Returns:
        tuple: (status_code, response_data)
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Memos-CLI/3.2.0",
    }

    if data:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data else None,
        headers=headers,
        method=method,
    )

    ssl_context = ssl.create_default_context()

    last_error = None
    last_status = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = calculate_retry_delay(attempt)
            print(f"   🔄 网络重试 {attempt}/{max_retries}（等待 {delay:.1f} 秒）...")
            time.sleep(delay)

        try:
            # 分离连接超时和读取超时
            with urllib.request.urlopen(req, context=ssl_context, timeout=None) as response:
                # 设置 socket 超时
                response.fp.raw._sock.settimeout(read_timeout)
                response_data = response.read().decode("utf-8")
                return response.status, json.loads(response_data) if response_data else {}

        except urllib.error.HTTPError as e:
            last_status = e.code
            # 4xx 错误不需要重试（客户端错误）
            if 400 <= e.code < 500:
                try:
                    return e.code, json.loads(e.read().decode("utf-8"))
                except:
                    return e.code, {"message": str(e)}
            # 5xx 错误需要重试
            try:
                last_error = json.loads(e.read().decode("utf-8")).get("message", str(e))
            except:
                last_error = str(e)

        except urllib.error.URLError as e:
            last_error = f"连接错误: {e.reason}"
            last_status = 0

        except socket.timeout:
            last_error = "连接超时"
            last_status = 0

        except ssl.SSLError as e:
            last_error = f"SSL错误: {str(e)}"
            last_status = 0

        except Exception as e:
            last_error = f"未知错误: {str(e)}"
            last_status = 500

    # 所有重试都失败了
    return last_status or 500, {"message": last_error or "请求失败"}


def upload_attachment(site_url, token, filepath, encoded_data=None, max_retries=DEFAULT_MAX_RETRIES):
    """上传附件（使用独立的 encode_file_to_base64 函数）

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        filepath: 文件路径
        encoded_data: 可选，已编码的 base64 数据字典（包含 filename, mime_type, base64_content）
        max_retries: 最大重试次数
    """
    if encoded_data:
        # 使用已编码的数据
        filename = encoded_data["filename"]
        mime_type = encoded_data["mime_type"]
        base64_content = encoded_data["base64_content"]
        size_human = encoded_data.get("size_human", "unknown")
    else:
        # 使用独立的编码函数
        result = encode_file_to_base64(filepath)
        if not result:
            return None

        filename = result["filename"]
        mime_type = result["mime_type"]
        base64_content = result["base64_content"]
        size_human = result["size_human"]

    # 上传
    url = f"{site_url}/api/v1/attachments"
    data = {"filename": filename, "type": mime_type, "content": base64_content}

    print(f"📤 上传: {filename} ({mime_type}, {size_human})")

    last_error = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            delay = calculate_retry_delay(attempt)
            print(f"   🔄 上传重试 {attempt}/{max_retries}（等待 {delay:.1f} 秒）...")
            time.sleep(delay)

        status, response = make_request("POST", url, token, data, max_retries=1)

        if status == 200:
            att_name = response.get("name")
            print(f"✅ 成功: {att_name}")
            return att_name
        else:
            last_error = response.get("message", "Unknown error")
            # 4xx 错误不重试
            if 400 <= status < 500:
                print(f"❌ 失败: {last_error}")
                return None

    print(f"❌ 失败: {last_error}")
    return None


def upload_attachments(
    site_url, token, filepaths, base64_files=None, max_retries=DEFAULT_MAX_RETRIES
):
    """批量上传附件 - 队列方式顺序上传，支持指数退避重试

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        filepaths: 原始文件路径列表
        base64_files: 已编码的 .b64 文件路径列表
        max_retries: 最大重试次数
    """
    attachments = []
    failed_uploads = []

    # 构建上传队列
    upload_queue = []

    # 添加原始文件到队列
    if filepaths:
        for filepath in filepaths:
            upload_queue.append({"type": "file", "path": filepath})

    # 添加已编码文件到队列
    if base64_files:
        for b64_filepath in base64_files:
            upload_queue.append({"type": "base64", "path": b64_filepath})

    total = len(upload_queue)
    if total == 0:
        return attachments

    print(f"\n📎 队列上传 {total} 个附件（指数退避重试）...")
    print(f"{'=' * 60}\n")

    # 顺序处理队列
    for i, item in enumerate(upload_queue, 1):
        filepath = item["path"]
        filename = os.path.basename(filepath)
        print(f"[{i}/{total}] 准备上传: {filename}")

        att_name = None
        last_error = None

        # 使用内置的指数退避重试
        if item["type"] == "file":
            att_name = upload_attachment(site_url, token, filepath, max_retries=max_retries)
        else:  # base64
            encoded_data = load_base64_from_file(filepath)
            if encoded_data:
                att_name = upload_attachment(site_url, token, None, encoded_data, max_retries=max_retries)

        if att_name:
            attachments.append(att_name)
            print(f"   ✅ 上传成功 ({len(attachments)}/{total})\n")
        else:
            failed_uploads.append({"file": filename, "error": "上传失败"})
            print(f"   ❌ 上传失败: {filename}\n")

        # 上传间隔，避免请求过快
        if i < total:
            time.sleep(0.5)

    # 上传总结
    print(f"{'=' * 60}")
    print(f"📊 上传完成: {len(attachments)}/{total} 个成功")

    if failed_uploads:
        print(f"\n❌ 失败文件 ({len(failed_uploads)} 个):")
        for fail in failed_uploads:
            print(f"   - {fail['file']}")
    print()

    return attachments


def delete_attachment(site_url, token, attachment_name):
    """删除已上传的附件"""
    url = f"{site_url}/api/v1/{attachment_name}"
    status, response = make_request("DELETE", url, token)
    return status == 200


def list_attachments(site_url, token, page_size=50, page_token=None, filter_str=None, order_by=None):
    """列出附件

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        page_size: 每页数量（默认50，最大1000）
        page_token: 分页令牌
        filter_str: 过滤条件，如 'mime_type=="image/png"' 或 'filename.contains("test")'
        order_by: 排序，如 'create_time desc' 或 'filename asc'

    Returns:
        dict: 包含 attachments, nextPageToken, totalSize 的字典
    """
    params = [f"pageSize={page_size}"]
    if page_token:
        params.append(f"pageToken={page_token}")
    if filter_str:
        params.append(f"filter={quote(filter_str)}")
    if order_by:
        params.append(f"orderBy={quote(order_by)}")

    url = f"{site_url}/api/v1/attachments?{'&'.join(params)}"
    status, response = make_request("GET", url, token)

    if status == 200:
        return response
    else:
        print(f"❌ 列出附件失败: {status} - {response.get('message', 'Unknown error')}")
        return None


def get_attachment(site_url, token, attachment_id):
    """获取单个附件详情

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        attachment_id: 附件 ID（如 'xxxxx' 或 'attachments/xxxxx'）

    Returns:
        dict: 附件详情
    """
    # 支持 attachments/xxxxx 或纯 ID 格式
    if not attachment_id.startswith("attachments/"):
        attachment_id = f"attachments/{attachment_id}"

    url = f"{site_url}/api/v1/{attachment_id}"
    status, response = make_request("GET", url, token)

    if status == 200:
        return response
    else:
        print(f"❌ 获取附件失败: {status} - {response.get('message', 'Unknown error')}")
        return None


def update_attachment(site_url, token, attachment_id, filename=None, content_base64=None,
                      external_link=None, mime_type=None, memo=None):
    """更新附件

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        attachment_id: 附件 ID
        filename: 新文件名
        content_base64: 新内容（Base64 编码）
        external_link: 外部链接
        mime_type: MIME 类型
        memo: 关联的 Memo（格式: memos/xxxxx）

    Returns:
        dict: 更新后的附件详情
    """
    # 支持 attachments/xxxxx 或纯 ID 格式
    if not attachment_id.startswith("attachments/"):
        attachment_id = f"attachments/{attachment_id}"

    update_fields = []
    data = {}

    if filename is not None:
        data["filename"] = filename
        update_fields.append("filename")
    if mime_type is not None:
        data["type"] = mime_type
        update_fields.append("type")
    if content_base64 is not None:
        data["content"] = content_base64
        update_fields.append("content")
    if external_link is not None:
        data["externalLink"] = external_link
        update_fields.append("externalLink")
    if memo is not None:
        data["memo"] = memo
        update_fields.append("memo")

    if not update_fields:
        print("❌ 没有需要更新的字段")
        return None

    url = f"{site_url}/api/v1/{attachment_id}?updateMask={','.join(update_fields)}"
    status, response = make_request("PATCH", url, token, data)

    if status == 200:
        return response
    else:
        print(f"❌ 更新附件失败: {status} - {response.get('message', 'Unknown error')}")
        return None


def print_attachment_detail(att):
    """打印附件详情"""
    print(f"\n📎 附件详情:\n")
    print(f"  名称: {att.get('name', 'N/A')}")
    print(f"  文件名: {att.get('filename', 'N/A')}")
    print(f"  类型: {att.get('type', 'N/A')}")
    print(f"  大小: {att.get('size', 'N/A')}")

    create_time = att.get('createTime')
    if create_time:
        print(f"  创建时间: {create_time}")

    external_link = att.get('externalLink')
    if external_link:
        print(f"  外部链接: {external_link}")

    memo = att.get('memo')
    if memo:
        print(f"  关联 Memo: {memo}")


def cleanup_attachments(site_url, token, attachment_names):
    """清理已上传但未关联的附件"""
    if not attachment_names:
        return
    print(f"\n🧹 清理未关联附件...")
    for name in attachment_names:
        if delete_attachment(site_url, token, name):
            print(f"   ✅ 已删除: {name}")
        else:
            print(f"   ⚠️ 删除失败: {name}")


def list_orphaned_attachments(site_url, token, page_size=100):
    """列出所有未使用的附件（memo 字段为空）

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        page_size: 每页数量

    Returns:
        list: 未使用的附件列表
    """
    all_orphaned = []
    page_token = None

    while True:
        params = [f"pageSize={page_size}"]
        if page_token:
            params.append(f"pageToken={page_token}")

        url = f"{site_url}/api/v1/attachments?{'&'.join(params)}"
        status, response = make_request("GET", url, token)

        if status != 200:
            print(f"❌ 获取附件列表失败: {status}")
            break

        attachments = response.get("attachments", [])

        # 过滤出 memo 为空的附件
        for att in attachments:
            if not att.get("memo"):
                all_orphaned.append(att)

        # 检查是否有更多数据
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_orphaned


def cleanup_orphaned_attachments(site_url, token, force=False):
    """清理所有未使用的附件

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        force: 是否强制删除（不确认）

    Returns:
        int: 删除的附件数量
    """
    print("🔍 正在扫描未使用的附件...")
    orphaned = list_orphaned_attachments(site_url, token)

    if not orphaned:
        print("✅ 没有发现未使用的附件")
        return 0

    total_size = sum(int(att.get("size", 0)) for att in orphaned)
    total_size_mb = total_size / 1024 / 1024

    print(f"\n📎 发现 {len(orphaned)} 个未使用的附件 (共 {total_size_mb:.2f} MB):\n")

    for i, att in enumerate(orphaned, 1):
        name = att.get("name", "N/A")
        filename = att.get("filename", "N/A")
        size = int(att.get("size", 0))
        size_kb = size / 1024
        create_time = att.get("createTime", "")

        print(f"{i}. {name}")
        print(f"   文件名: {filename}")
        print(f"   大小: {size_kb:.1f} KB")
        if create_time:
            print(f"   创建时间: {create_time}")
        print()

    # 确认删除
    if not force:
        confirm = input(f"⚠️ 确认删除以上 {len(orphaned)} 个未使用的附件? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ 已取消")
            return 0

    # 执行删除
    deleted_count = 0
    failed_count = 0

    print("\n🧹 正在清理...")
    for att in orphaned:
        name = att.get("name")
        if delete_attachment(site_url, token, name):
            print(f"   ✅ 已删除: {name}")
            deleted_count += 1
        else:
            print(f"   ❌ 删除失败: {name}")
            failed_count += 1
        time.sleep(0.2)  # 避免请求过快

    print(f"\n📊 清理完成: {deleted_count} 个成功, {failed_count} 个失败")
    return deleted_count


def find_duplicate_memo(site_url, token, content, visibility):
    """查找是否存在相同内容和可见性的 Memo（用于幂等性检查）

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        content: Memo 内容
        visibility: 可见性

    Returns:
        dict: 找到的 Memo 对象，未找到返回 None
    """
    # 使用 CEL 过滤器精确匹配
    filter_str = f'visibility == "{visibility}"'
    url = f"{site_url}/api/v1/memos?pageSize=20&filter={quote(filter_str)}"

    status, response = make_request("GET", url, token, max_retries=1)

    if status == 200:
        memos = response.get("memos", [])
        for memo in memos:
            if not isinstance(memo, dict):
                continue
            # 精确匹配内容
            if memo.get("content", "").strip() == content.strip():
                return memo

    return None


def get_memo_by_id(site_url, token, memo_name):
    """根据 ID 获取 Memo 详情

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        memo_name: Memo 名称 (如: memos/xxxxx)

    Returns:
        dict: Memo 对象，失败返回 None
    """
    url = f"{site_url}/api/v1/{memo_name}"
    status, response = make_request("GET", url, token, max_retries=1)

    if status == 200:
        return response
    return None


def check_memo_completeness(memo, expected_attachments):
    """检查 Memo 是否完整（附件数量是否匹配）

    Args:
        memo: Memo 对象
        expected_attachments: 预期的附件列表

    Returns:
        tuple: (is_complete, missing_count) - 是否完整，缺失附件数
    """
    if not memo:
        return False, len(expected_attachments)

    existing_atts = memo.get("attachments", [])
    existing_count = len(existing_atts)
    expected_count = len(expected_attachments)

    if existing_count >= expected_count:
        return True, 0
    return False, expected_count - existing_count


def create_memo(
    site_url,
    token,
    content,
    visibility="PRIVATE",
    pinned=False,
    attachments=None,
    filepaths=None,
    base64_files=None,
    max_retries=DEFAULT_MAX_RETRIES,
    retry_delay=None,
    strict_attachments=True,
    state="NORMAL",
    create_time=None,
    display_time=None,
):
    """创建 Memo，支持预上传模式和指数退避重试

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        content: Memo 内容
        visibility: 可见性 (PRIVATE/PROTECTED/PUBLIC)
        pinned: 是否置顶
        attachments: 已上传附件 name 列表（预上传模式）
        filepaths: 原始文件路径列表
        base64_files: 已编码的 .b64 文件路径列表
        max_retries: 创建失败时最大重试次数
        strict_attachments: 严格附件模式（True=必须全部上传成功才创建）
        state: Memo 状态 (NORMAL/ARCHIVED)
        create_time: 创建时间 (ISO 8601 格式)
        display_time: 显示时间 (ISO 8601 格式)
    """
    all_attachments = list(attachments) if attachments else []
    uploaded_attachments = []
    total_files = (len(filepaths) if filepaths else 0) + (
        len(base64_files) if base64_files else 0
    )

    # 阶段1：上传文件（如果未预上传）
    if total_files > 0 and not attachments:
        print(f"\n📎 阶段1：上传 {total_files} 个附件...")
        uploaded_attachments = upload_attachments(
            site_url, token, filepaths, base64_files, max_retries=max_retries
        )
        all_attachments.extend(uploaded_attachments)

        # 严格模式：检查附件是否全部上传成功
        if strict_attachments and len(uploaded_attachments) < total_files:
            failed_count = total_files - len(uploaded_attachments)
            print(f"\n❌ 严格模式: {failed_count} 个附件上传失败，中止创建")
            print(f"🧹 清理已上传的 {len(uploaded_attachments)} 个附件...")

            if uploaded_attachments:
                cleanup_attachments(site_url, token, uploaded_attachments)

            print("💡 提示: 使用 --no-strict 可跳过此检查（创建部分附件的 memo）")
            return None

        if len(uploaded_attachments) < total_files:
            print(
                f"⚠️ 部分文件上传失败，将使用已上传的 {len(uploaded_attachments)} 个文件"
            )

    # 阶段2：创建 Memo（带重试）
    url = f"{site_url}/api/v1/memos"
    data = {
        "content": content,
        "visibility": visibility,
        "pinned": pinned,
        "state": state,
    }

    if create_time:
        data["createTime"] = create_time

    if display_time:
        data["displayTime"] = display_time

    if all_attachments:
        data["attachments"] = [{"name": name} for name in all_attachments if name]

    print(f"\n📝 阶段2：创建 Memo...")

    # 创建 Memo 带重试，每次失败后检查并清理可能存在的不完整 Memo
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            delay = calculate_retry_delay(attempt)
            print(f"   🔄 重试 {attempt}/{max_retries}（等待 {delay:.1f} 秒）...")
            time.sleep(delay)

            # 重试前检查是否存在不完整的重复 Memo
            existing = find_duplicate_memo(site_url, token, content, visibility)
            if existing:
                existing_name = existing.get("name")
                print(f"   🔍 发现已存在的 Memo: {existing_name}，根据 ID 查询详情...")

                # 根据 ID 获取最新详情
                memo_detail = get_memo_by_id(site_url, token, existing_name)

                if memo_detail:
                    # 检查完整性
                    is_complete, missing_count = check_memo_completeness(memo_detail, all_attachments)

                    if is_complete:
                        print(f"   ✅ Memo 完整，附件齐全")
                        memo_id = existing_name.split("/")[-1]
                        print(f"\n📝 URL: {site_url}/memos/{memo_id}")
                        return memo_detail
                    else:
                        print(f"   ⚠️ Memo 不完整，缺失 {missing_count} 个附件")
                        print(f"   🗑️ 删除不完整的 Memo...")
                        delete_memo(site_url, token, existing_name)
                else:
                    print(f"   ⚠️ 无法获取 Memo 详情，跳过检查")

        # POST 创建请求不内部重试，避免重复创建；重试由外层循环控制
        status, response = make_request("POST", url, token, data, max_retries=0)

        if status == 200:
            memo_name = response.get("name", "N/A")
            print(f"\n✅ Memo 创建成功!")
            print(f"   名称: {memo_name}")
            print(f"   可见性: {response.get('visibility', 'N/A')}")

            tags = response.get("tags", [])
            if tags:
                print(f"   标签: {', '.join(tags)}")

            attached = response.get("attachments", [])
            if attached:
                print(f"   附件: {len(attached)} 个")

            memo_id = memo_name.split("/")[-1]
            print(f"\n📝 URL: {site_url}/memos/{memo_id}")
            return response

    # 所有重试都失败
    error_msg = response.get("message", "未知错误") if response else "请求失败"
    print(f"\n❌ 创建失败: {error_msg}")

    # 清理已上传但未关联的附件
    if uploaded_attachments:
        print("\n🧹 清理未关联附件...")
        cleanup_attachments(site_url, token, uploaded_attachments)

    return None


def list_memos(site_url, token, page_size=10, state=None, order_by=None, filter_str=None, show_deleted=False):
    """列出 Memo

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        page_size: 每页数量
        state: 状态过滤 (NORMAL/ARCHIVED/STATE_UNSPECIFIED)
        order_by: 排序字段 (pinned, display_time, create_time, update_time)
        filter_str: 过滤条件 (CEL 表达式)
        show_deleted: 是否显示已删除
    """
    params = [f"pageSize={page_size}"]

    if state:
        params.append(f"state={state}")
    if order_by:
        params.append(f"orderBy={quote(order_by)}")
    if filter_str:
        params.append(f"filter={quote(filter_str)}")
    if show_deleted:
        params.append("showDeleted=true")

    url = f"{site_url}/api/v1/memos?{'&'.join(params)}"
    status, response = make_request("GET", url, token)

    if status == 200:
        memos = response.get("memos", [])
        next_token = response.get("nextPageToken")

        print(f"\n📋 找到 {len(memos)} 条 Memo:\n")

        for i, memo in enumerate(memos, 1):
            if not isinstance(memo, dict):
                continue
            name = memo.get("name", "N/A")
            memo_state = memo.get("state", "NORMAL")
            content = memo.get("content", "")[:60]
            if len(memo.get("content", "")) > 60:
                content += "..."
            vis = memo.get("visibility", "N/A")
            tags = ", ".join(memo.get("tags", []))
            att_count = len(memo.get("attachments", []))
            pinned = "📌 " if memo.get("pinned") else ""

            print(f"{i}. {pinned}{name} [{memo_state}]")
            print(f"   {content}")
            print(f"   可见性: {vis} | 标签: [{tags}] | 附件: {att_count}")
            print()

        if next_token:
            print(f"📄 更多数据可用，使用 --page-token {next_token}")
    else:
        print(f"❌ 获取失败: {status}")


def get_memo(site_url, token, memo_name):
    """查看 Memo 详情"""
    url = f"{site_url}/api/v1/{memo_name}"
    status, response = make_request("GET", url, token)

    if status == 200:
        print(f"\n📄 Memo 详情:\n")
        print(f"  名称: {response.get('name', 'N/A')}")
        print(f"  内容:\n{response.get('content', 'N/A')}\n")
        print(f"  可见性: {response.get('visibility', 'N/A')}")
        print(f"  标签: {', '.join(response.get('tags', []))}")
        print(f"  置顶: {'是' if response.get('pinned') else '否'}")

        attachments = response.get("attachments", [])
        if attachments:
            print(f"\n  附件 ({len(attachments)} 个):")
            for att in attachments:
                if isinstance(att, dict):
                    print(
                        f"    - {att.get('filename', 'N/A')} ({att.get('type', 'N/A')})"
                    )
    else:
        print(f"❌ 获取失败: {status}")


def update_memo(
    site_url,
    token,
    memo_name,
    content=None,
    visibility=None,
    pinned=None,
    state=None,
    filepaths=None,
    base64_files=None,
    max_retries=DEFAULT_MAX_RETRIES,
    retry_delay=None,
):
    """更新 Memo，支持上传新附件和指数退避重试

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        memo_name: Memo 名称
        content: 新内容
        visibility: 可见性
        pinned: 是否置顶
        state: 状态 (NORMAL/ARCHIVED)
        filepaths: 新文件路径列表
        base64_files: 新 .b64 文件路径列表
        max_retries: 更新失败时最大重试次数
    """
    # 阶段1：上传新附件（如果有）
    new_attachments = []
    total_files = (len(filepaths) if filepaths else 0) + (
        len(base64_files) if base64_files else 0
    )

    if total_files > 0:
        print(f"\n📎 阶段1：上传 {total_files} 个新附件...")
        new_attachments = upload_attachments(
            site_url, token, filepaths, base64_files, max_retries=max_retries
        )

        if len(new_attachments) < total_files:
            print(f"⚠️ 部分新文件上传失败，将使用已上传的 {len(new_attachments)} 个文件")

    # 获取现有附件（用于合并）
    existing_attachments = []
    if new_attachments:
        print(f"\n📋 获取现有附件...")
        get_url = f"{site_url}/api/v1/{memo_name}"
        status, response = make_request("GET", get_url, token, max_retries=1)

        if status == 200 and isinstance(response, dict):
            existing_attachments = [
                att.get("name")
                for att in response.get("attachments", [])
                if isinstance(att, dict) and att.get("name")
            ]
            print(f"   现有附件: {len(existing_attachments)} 个")

    # 阶段2：更新 Memo
    update_fields = []
    data = {}

    if content is not None:
        data["content"] = content
        update_fields.append("content")
    if visibility is not None:
        data["visibility"] = visibility
        update_fields.append("visibility")
    if pinned is not None:
        data["pinned"] = pinned
        update_fields.append("pinned")
    if state is not None:
        data["state"] = state
        update_fields.append("state")

    # 合并新旧附件
    if new_attachments:
        all_attachments = existing_attachments + new_attachments
        data["attachments"] = [{"name": name} for name in all_attachments if name]
        update_fields.append("attachments")

    if not update_fields:
        if new_attachments and len(new_attachments) < total_files:
            print("❌ 部分文件上传失败且没有其他字段需要更新")
        else:
            print("ℹ️ 没有需要更新的内容")
        return

    url = f"{site_url}/api/v1/{memo_name}?updateMask={','.join(update_fields)}"

    print(f"\n📝 阶段2：更新 Memo...")

    status, response = make_request("PATCH", url, token, data, max_retries=max_retries)

    if status == 200:
        print(f"✅ 更新成功: {memo_name}")
        if new_attachments:
            print(f"   新增附件: {len(new_attachments)} 个")
            attached = response.get("attachments", [])
            if attached:
                print(f"   总附件数: {len(attached)} 个")
        return response
    else:
        error_msg = response.get("message", "未知错误")
        print(f"❌ 更新失败 ({status}): {error_msg}")

        # 清理本次新上传但未能关联的附件
        if new_attachments:
            print(f"\n🧹 清理本次上传的 {len(new_attachments)} 个附件...")
            cleanup_attachments(site_url, token, new_attachments)

        return None


def delete_memo(site_url, token, memo_name, cleanup_attachments_flag=False):
    """删除 Memo

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        memo_name: Memo 名称
        cleanup_attachments_flag: 是否同时清理关联的附件
    """
    # 如果需要清理附件，先获取附件列表
    memo_attachments = []
    if cleanup_attachments_flag:
        get_url = f"{site_url}/api/v1/{memo_name}"
        status, response = make_request("GET", get_url, token, max_retries=1)
        if status == 200 and isinstance(response, dict):
            memo_attachments = [
                att.get("name")
                for att in response.get("attachments", [])
                if isinstance(att, dict) and att.get("name")
            ]
            if memo_attachments:
                print(f"📎 该 Memo 有 {len(memo_attachments)} 个关联附件")

    url = f"{site_url}/api/v1/{memo_name}"
    status, response = make_request("DELETE", url, token)

    if status == 200:
        print(f"✅ 已删除: {memo_name}")

        # 清理关联的附件
        if cleanup_attachments_flag and memo_attachments:
            print(f"\n🧹 清理关联的 {len(memo_attachments)} 个附件...")
            cleanup_attachments(site_url, token, memo_attachments)

    elif status == 404:
        print(f"ℹ️ Memo 不存在或已被删除: {memo_name}")
    elif status == 500:
        print(f"⚠️ 服务器返回 500 错误，但删除操作可能已成功")
        print(f"   建议: 请验证 memo 是否已被删除")
    else:
        error_msg = response.get("message", "未知错误")
        print(f"❌ 删除失败 ({status}): {error_msg}")


def list_memo_attachments(site_url, token, memo_name):
    """列出 Memo 的所有附件

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        memo_name: Memo 名称 (如: memos/xxxxx)
    """
    url = f"{site_url}/api/v1/{memo_name}/attachments"
    status, response = make_request("GET", url, token)

    if status == 200:
        attachments = response.get("attachments", [])
        print(f"\n📎 Memo {memo_name} 的附件 ({len(attachments)} 个):\n")

        for i, att in enumerate(attachments, 1):
            if not isinstance(att, dict):
                continue
            name = att.get("name", "N/A")
            filename = att.get("filename", "N/A")
            mime_type = att.get("type", "N/A")
            size = att.get("size", "N/A")

            print(f"{i}. {name}")
            print(f"   文件名: {filename}")
            print(f"   类型: {mime_type} | 大小: {size}")
            print()

        return attachments
    else:
        print(f"❌ 获取附件列表失败: {status}")
        return None


def set_memo_attachments(site_url, token, memo_name, attachment_names):
    """设置 Memo 的附件（完全替换现有附件）

    Args:
        site_url: Memos 站点 URL
        token: 访问令牌
        memo_name: Memo 名称
        attachment_names: 附件名称列表 (如: ["attachments/xxxxx", "attachments/yyyyy"])

    Returns:
        更新后的 Memo 对象
    """
    url = f"{site_url}/api/v1/{memo_name}:setAttachments"
    data = {
        "attachments": [{"name": name} for name in attachment_names if name]
    }

    status, response = make_request("PATCH", url, token, data)

    if status == 200:
        print(f"✅ 已设置附件: {memo_name}")
        attachments = response.get("attachments", [])
        print(f"   附件数量: {len(attachments)} 个")
        return response
    else:
        error_msg = response.get("message", "未知错误")
        print(f"❌ 设置附件失败 ({status}): {error_msg}")
        return None


def search_memos(site_url, token, keyword):
    """搜索 Memos"""
    encoded_filter = quote(f'content.contains("{keyword}")')
    url = f"{site_url}/api/v1/memos?filter={encoded_filter}"

    status, response = make_request("GET", url, token)

    if status == 200:
        memos = response.get("memos", [])
        print(f"\n🔍 搜索 '{keyword}': 找到 {len(memos)} 条结果\n")

        for i, memo in enumerate(memos, 1):
            if not isinstance(memo, dict):
                continue
            name = memo.get("name", "N/A")
            content = memo.get("content", "")[:80].replace("\n", " ")
            if len(memo.get("content", "")) > 80:
                content += "..."
            print(f"{i}. {name}")
            print(f"   {content}")
            print()
    else:
        print(f"❌ 搜索失败: {status}")


def main():
    parser = argparse.ArgumentParser(
        description="Memos CLI - 完整版 Memos 管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:

【创建 Memo】
  # 纯文本
  %(prog)s create "今天天气不错"

  # 带标签
  %(prog)s create "今天心情很好" -t 生活 -t 心情

  # 上传本地文件作为附件
  %(prog)s create "旅行照片" -f ~/photos/photo1.jpg -f ~/photos/photo2.png

  # 混合使用：本地文件 + 已上传附件
  %(prog)s create "会议记录" -f ~/recordings/meeting.mp3 -a attachments/xxxxx

  # 公开 Memo
  %(prog)s create "公开分享" --visibility PUBLIC

  # 置顶
  %(prog)s create "重要事项" --pinned

  # 失败时自动重试
  %(prog)s create "重要内容" -f photo.jpg --retry

【列出 Memo】
  %(prog)s list
  %(prog)s list --page-size 20

【查看 Memo】
  %(prog)s get memos/xxxxx

【更新 Memo】
  %(prog)s update memos/xxxxx --content "新内容"
  %(prog)s update memos/xxxxx --visibility PUBLIC
  %(prog)s update memos/xxxxx --pinned true

【删除 Memo】
  %(prog)s delete memos/xxxxx

【搜索 Memo】
  %(prog)s search "关键词"

支持文件类型:
  图片: jpg, jpeg, png, gif, webp, svg
  视频: mp4, mov, avi, webm
  音频: mp3, wav, ogg, m4a
  文档: pdf, doc, docx, xls, xlsx, txt, md

限制:
  - 单个文件 ≤50MB
  - 自动检测 MIME 类型

【Base64 编码】
  # 编码文件为 Base64（输出到控制台）
  %(prog)s encode ~/photos/photo.jpg

  # 编码并保存为 .b64 文件
  %(prog)s encode ~/photos/photo.jpg --save

  # 指定输出目录
  %(prog)s encode ~/photos/photo.jpg --save --output-dir ~/encoded

  # 批量编码多个文件
  %(prog)s encode ~/photos/*.jpg --save

【附件管理】
  # 列出所有附件
  %(prog)s att-list
  %(prog)s att-list --page-size 20

  # 过滤附件（按类型）
  %(prog)s att-list --filter 'mime_type=="image/png"'

  # 过滤附件（按文件名）
  %(prog)s att-list --filter 'filename.contains("test")'

  # 排序
  %(prog)s att-list --order-by "create_time desc"

  # 获取附件详情
  %(prog)s att-get attachments/xxxxx
  %(prog)s att-get xxxxx

  # 更新附件文件名
  %(prog)s att-update attachments/xxxxx --filename "new_name.jpg"

  # 更新附件内容
  %(prog)s att-update attachments/xxxxx --file ~/new_content.jpg

  # 更新附件关联的 Memo
  %(prog)s att-update attachments/xxxxx --memo memos/yyyyy

  # 删除附件
  %(prog)s att-delete attachments/xxxxx
  %(prog)s att-delete attachments/xxxxx --force  # 不确认直接删除
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # Create command
    create_parser = subparsers.add_parser("create", help="创建 Memo")
    create_parser.add_argument("content", help="Memo 内容")
    create_parser.add_argument(
        "-f",
        "--file",
        action="append",
        help="本地文件路径 (可多次使用，自动上传并附加)",
    )
    create_parser.add_argument(
        "-a",
        "--attachment",
        action="append",
        help="已上传附件 name (可多次使用, 如: attachments/xxxxx)",
    )
    create_parser.add_argument("-t", "--tag", action="append", help="标签 (可多次使用)")
    create_parser.add_argument(
        "--visibility", choices=["PRIVATE", "PROTECTED", "PUBLIC"], default="PRIVATE"
    )
    create_parser.add_argument("--pinned", action="store_true", help="置顶")
    create_parser.add_argument(
        "--max-retries", type=int, default=3, help="失败时最大重试次数（默认3次）"
    )
    create_parser.add_argument(
        "--retry-delay", type=int, default=1, help="重试间隔秒数（默认1秒）"
    )
    create_parser.add_argument(
        "-b",
        "--base64-file",
        action="append",
        help="Base64 编码文件路径 (.b64 格式，可多次使用)",
    )
    create_parser.add_argument(
        "--no-strict",
        action="store_true",
        help="宽松模式：允许部分附件失败时仍创建 Memo（默认严格模式）",
    )
    create_parser.add_argument(
        "--state", choices=["NORMAL", "ARCHIVED"], default="NORMAL",
        help="Memo 状态（默认 NORMAL）"
    )
    create_parser.add_argument(
        "--create-time", dest="create_time", help="创建时间 (ISO 8601 格式，如: 2024-01-15T10:30:00Z)"
    )
    create_parser.add_argument(
        "--display-time", dest="display_time", help="显示时间 (ISO 8601 格式，如: 2024-01-15T10:30:00Z)"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="列出 Memo")
    list_parser.add_argument("--page-size", type=int, default=10, help="每页数量（默认10）")
    list_parser.add_argument(
        "--state", choices=["NORMAL", "ARCHIVED", "STATE_UNSPECIFIED"],
        help="状态过滤"
    )
    list_parser.add_argument(
        "--order-by", help="排序字段（如: pinned desc, display_time desc）"
    )
    list_parser.add_argument(
        "--filter", help="过滤条件 (CEL 表达式，如: 'visibility == \"PUBLIC\"')"
    )
    list_parser.add_argument(
        "--show-deleted", action="store_true", help="显示已删除的 Memo"
    )

    # Get command
    get_parser = subparsers.add_parser("get", help="查看 Memo")
    get_parser.add_argument("name", help="Memo name (如: memos/xxxxx)")

    # Update command
    update_parser = subparsers.add_parser("update", help="更新 Memo")
    update_parser.add_argument("name", help="Memo name")
    update_parser.add_argument("--content", help="新内容")
    update_parser.add_argument(
        "--visibility", choices=["PRIVATE", "PROTECTED", "PUBLIC"]
    )
    update_parser.add_argument(
        "--pinned", type=lambda x: x.lower() == "true", help="true/false"
    )
    update_parser.add_argument(
        "--state", choices=["NORMAL", "ARCHIVED"], help="Memo 状态"
    )
    update_parser.add_argument(
        "-f",
        "--file",
        action="append",
        help="上传新附件 (可多次使用)",
    )
    update_parser.add_argument(
        "-b",
        "--base64-file",
        action="append",
        help="Base64 编码文件路径 (.b64 格式，可多次使用)",
    )
    update_parser.add_argument(
        "--max-retries", type=int, default=3, help="失败时最大重试次数（默认3次）"
    )
    update_parser.add_argument(
        "--retry-delay", type=int, default=1, help="重试间隔秒数（默认1秒）"
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="删除 Memo")
    delete_parser.add_argument("name", help="Memo name")
    delete_parser.add_argument("--cleanup-attachments", action="store_true",
                               help="删除 Memo 后同时清理关联的附件")

    # Search command
    search_parser = subparsers.add_parser("search", help="搜索 Memo")
    search_parser.add_argument("keyword", help="搜索关键词")

    # Encode command
    encode_parser = subparsers.add_parser("encode", help="将文件编码为 Base64")
    encode_parser.add_argument(
        "files", nargs="+", help="要编码的文件路径（支持通配符）"
    )
    encode_parser.add_argument(
        "-s", "--save", action="store_true", help="保存为 .b64 文件（默认输出到控制台）"
    )
    encode_parser.add_argument(
        "-o", "--output-dir", help="指定输出目录（仅与 --save 一起使用）"
    )
    encode_parser.add_argument(
        "--clipboard", action="store_true", help="复制到剪贴板（需要 pyperclip）"
    )

    # ==================== Memo 附件命令 ====================

    # Memo attachments list command
    memo_att_list_parser = subparsers.add_parser("memo-att-list", help="列出 Memo 的附件",
                                                  aliases=["memo-attachments"])
    memo_att_list_parser.add_argument("name", help="Memo name (如: memos/xxxxx)")

    # Memo attachments set command
    memo_att_set_parser = subparsers.add_parser("memo-att-set", help="设置 Memo 的附件（完全替换）",
                                                aliases=["set-memo-attachments"])
    memo_att_set_parser.add_argument("name", help="Memo name")
    memo_att_set_parser.add_argument("-a", "--attachment", action="append", required=True,
                                      help="附件名称 (可多次使用, 如: attachments/xxxxx)")

    # ==================== 附件命令 ====================

    # Attachment list command
    att_list_parser = subparsers.add_parser("att-list", help="列出所有附件",
                                            aliases=["attachment-list", "attachments"])
    att_list_parser.add_argument("--page-size", type=int, default=50,
                                  help="每页数量（默认50，最大1000）")
    att_list_parser.add_argument("--filter", help="过滤条件，如 'mime_type==\"image/png\"' 或 'filename.contains(\"test\")'")
    att_list_parser.add_argument("--order-by", help="排序，如 'create_time desc' 或 'filename asc'")

    # Attachment get command
    att_get_parser = subparsers.add_parser("att-get", help="获取附件详情",
                                           aliases=["attachment-get"])
    att_get_parser.add_argument("id", help="附件 ID（如: xxxxx 或 attachments/xxxxx）")

    # Attachment update command
    att_update_parser = subparsers.add_parser("att-update", help="更新附件",
                                              aliases=["attachment-update"])
    att_update_parser.add_argument("id", help="附件 ID")
    att_update_parser.add_argument("--filename", help="新文件名")
    att_update_parser.add_argument("--file", "-f", help="新文件内容（本地文件路径，自动编码为 Base64）")
    att_update_parser.add_argument("--external-link", help="外部链接")
    att_update_parser.add_argument("--memo", help="关联的 Memo（格式: memos/xxxxx）")

    # Attachment delete command
    att_delete_parser = subparsers.add_parser("att-delete", help="删除附件",
                                              aliases=["attachment-delete"])
    att_delete_parser.add_argument("id", help="附件 ID")
    att_delete_parser.add_argument("--force", action="store_true", help="强制删除（不确认）")

    # Attachment cleanup command
    att_cleanup_parser = subparsers.add_parser("att-cleanup", help="清理未使用的附件（memo为空的附件）",
                                               aliases=["attachment-cleanup", "cleanup-attachments"])
    att_cleanup_parser.add_argument("--force", action="store_true", help="强制删除（不确认）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # encode 命令不需要环境变量
    if args.command == "encode":
        # 处理通配符
        import glob

        files = []
        for pattern in args.files:
            matched = glob.glob(pattern)
            if matched:
                files.extend(matched)
            elif os.path.exists(pattern):
                files.append(pattern)

        if not files:
            print("❌ 未找到文件")
            sys.exit(1)

        print(f"📝 准备编码 {len(files)} 个文件...\n")

        for filepath in files:
            result = encode_file_to_base64(filepath)
            if not result:
                continue

            if args.save:
                # 保存为 .b64 文件
                save_base64_to_file(filepath, args.output_dir)
            else:
                # 输出到控制台
                print(
                    f"📄 {result['filename']} ({result['mime_type']}, {result['size_human']})"
                )
                print(f"{'=' * 60}")
                # 截断显示（前200字符）
                content = result["base64_content"]
                if len(content) > 200:
                    print(content[:200] + f"... [{len(content)} chars total]")
                else:
                    print(content)
                print(f"{'=' * 60}\n")

                if args.clipboard:
                    try:
                        import pyperclip

                        pyperclip.copy(result["base64_content"])
                        print("✅ 已复制到剪贴板")
                    except ImportError:
                        print("⚠️ 请先安装 pyperclip: pip install pyperclip")
        return

    site_url, token = get_env_vars()

    if args.command == "create":
        content = args.content
        if args.tag:
            tags = " ".join([f"#{t}" for t in args.tag])
            content = f"{content}\n\n{tags}"

        create_memo(
            site_url,
            token,
            content,
            args.visibility,
            args.pinned,
            args.attachment,
            args.file,
            args.base64_file,
            args.max_retries,
            args.retry_delay,
            strict_attachments=not args.no_strict,
            state=args.state,
            create_time=args.create_time,
            display_time=args.display_time,
        )

    elif args.command == "list":
        list_memos(site_url, token, args.page_size, args.state, args.order_by, args.filter, args.show_deleted)

    elif args.command == "get":
        get_memo(site_url, token, args.name)

    elif args.command == "update":
        update_memo(
            site_url,
            token,
            args.name,
            args.content,
            args.visibility,
            args.pinned,
            args.state,
            args.file,
            args.base64_file,
            args.max_retries,
            args.retry_delay,
        )

    elif args.command == "delete":
        delete_memo(site_url, token, args.name, cleanup_attachments_flag=args.cleanup_attachments)

    elif args.command == "search":
        search_memos(site_url, token, args.keyword)

    # ==================== Memo 附件命令处理 ====================
    elif args.command in ["memo-att-list", "memo-attachments"]:
        list_memo_attachments(site_url, token, args.name)

    elif args.command in ["memo-att-set", "set-memo-attachments"]:
        set_memo_attachments(site_url, token, args.name, args.attachment)

    # ==================== 附件命令处理 ====================
    elif args.command in ["att-list", "attachment-list", "attachments"]:
        result = list_attachments(site_url, token, args.page_size, filter_str=args.filter, order_by=args.order_by)
        if result:
            attachments = result.get("attachments", [])
            total_size = result.get("totalSize", 0)
            next_token = result.get("nextPageToken")

            print(f"\n📎 找到 {len(attachments)} 个附件 (总计: {total_size}):\n")

            for i, att in enumerate(attachments, 1):
                if not isinstance(att, dict):
                    continue
                name = att.get("name", "N/A")
                filename = att.get("filename", "N/A")
                mime_type = att.get("type", "N/A")
                size = att.get("size", "N/A")
                create_time = att.get("createTime", "")

                print(f"{i}. {name}")
                print(f"   文件名: {filename}")
                print(f"   类型: {mime_type} | 大小: {size}")
                if create_time:
                    print(f"   创建时间: {create_time}")
                print()

            if next_token:
                print(f"📄 更多数据可用，使用 --page-token {next_token} 获取下一页")

    elif args.command in ["att-get", "attachment-get"]:
        att = get_attachment(site_url, token, args.id)
        if att:
            print_attachment_detail(att)

    elif args.command in ["att-update", "attachment-update"]:
        # 处理文件内容更新
        content_base64 = None
        mime_type = None
        if args.file:
            result = encode_file_to_base64(args.file)
            if result:
                content_base64 = result["base64_content"]
                # 如果没有指定 filename，使用新文件的文件名
                if not args.filename:
                    args.filename = result["filename"]
                # 自动检测 MIME 类型
                mime_type = result["mime_type"]
            else:
                print("❌ 读取文件失败")
                return

        att = update_attachment(
            site_url, token, args.id,
            filename=args.filename,
            content_base64=content_base64,
            external_link=args.external_link,
            mime_type=mime_type,
            memo=args.memo
        )
        if att:
            print(f"✅ 附件更新成功!")
            print_attachment_detail(att)

    elif args.command in ["att-delete", "attachment-delete"]:
        # 确认删除
        if not args.force:
            att_id = args.id
            if not att_id.startswith("attachments/"):
                att_id = f"attachments/{att_id}"

            confirm = input(f"⚠️ 确认删除附件 {att_id}? (y/N): ")
            if confirm.lower() != 'y':
                print("❌ 已取消")
                return

        att_id = args.id
        if not att_id.startswith("attachments/"):
            att_id = f"attachments/{att_id}"

        url = f"{site_url}/api/v1/{att_id}"
        status, response = make_request("DELETE", url, token)

        if status == 200:
            print(f"✅ 已删除附件: {att_id}")
        else:
            print(f"❌ 删除失败: {status} - {response.get('message', 'Unknown error')}")

    elif args.command in ["att-cleanup", "attachment-cleanup", "cleanup-attachments"]:
        cleanup_orphaned_attachments(site_url, token, force=args.force)


if __name__ == "__main__":
    main()
