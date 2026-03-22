#!/usr/bin/env python3
"""
Memos CLI - 完整版

支持功能:
- 纯文本内容 (支持 Markdown 和标签)
- 本地文件自动上传 (图片/视频/音频/文档)
- 完整的 CRUD 操作
- 搜索功能
- 网络波动自适应重试

环境变量:
- MEMOS_SITE_URL: Memos 实例 URL
- MEMOS_ACCESS_TOKEN: 访问令牌

作者: MoeWah (moewah.com)
版本: 3.2.0
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
    data = {"content": content, "visibility": visibility, "pinned": pinned}

    if all_attachments:
        data["attachments"] = [{"name": name} for name in all_attachments if name]

    print(f"\n📝 阶段2：创建 Memo...")

    status, response = make_request("POST", url, token, data, max_retries=max_retries)

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
    else:
        error_msg = response.get("message", "未知错误")
        print(f"\n❌ 创建失败 ({status}): {error_msg}")

        # 清理已上传但未关联的附件
        if uploaded_attachments:
            print("\n🧹 清理未关联附件...")
            cleanup_attachments(site_url, token, uploaded_attachments)

        return None


def list_memos(site_url, token, page_size=10):
    """列出 Memo"""
    url = f"{site_url}/api/v1/memos?pageSize={page_size}"
    status, response = make_request("GET", url, token)

    if status == 200:
        memos = response.get("memos", [])
        print(f"\n📋 找到 {len(memos)} 条 Memo:\n")

        for i, memo in enumerate(memos, 1):
            if not isinstance(memo, dict):
                continue
            name = memo.get("name", "N/A")
            content = memo.get("content", "")[:60]
            if len(memo.get("content", "")) > 60:
                content += "..."
            vis = memo.get("visibility", "N/A")
            tags = ", ".join(memo.get("tags", []))
            att_count = len(memo.get("attachments", []))

            print(f"{i}. {name}")
            print(f"   {content}")
            print(f"   可见性: {vis} | 标签: [{tags}] | 附件: {att_count}")
            print()
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


def delete_memo(site_url, token, memo_name):
    """删除 Memo"""
    url = f"{site_url}/api/v1/{memo_name}"
    status, response = make_request("DELETE", url, token)

    if status == 200:
        print(f"✅ 已删除: {memo_name}")
    elif status == 404:
        print(f"ℹ️ Memo 不存在或已被删除: {memo_name}")
    elif status == 500:
        print(f"⚠️ 服务器返回 500 错误，但删除操作可能已成功")
        print(f"   建议: 请验证 memo 是否已被删除")
    else:
        error_msg = response.get("message", "未知错误")
        print(f"❌ 删除失败 ({status}): {error_msg}")


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

    # List command
    list_parser = subparsers.add_parser("list", help="列出 Memo")
    list_parser.add_argument("--page-size", type=int, default=10)

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
        )

    elif args.command == "list":
        list_memos(site_url, token, args.page_size)

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
            args.file,
            args.base64_file,
            args.max_retries,
            args.retry_delay,
        )

    elif args.command == "delete":
        delete_memo(site_url, token, args.name)

    elif args.command == "search":
        search_memos(site_url, token, args.keyword)


if __name__ == "__main__":
    main()
