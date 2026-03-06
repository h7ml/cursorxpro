#!/usr/bin/env python3
"""
CursorX 导航链接获取工具
请求并解析 CursorX 的导航链接接口（支持双层 Base64 编码）
"""

import json
import base64
import requests
from datetime import datetime

# CursorX 配置
API_HOST = "https://cursorxpro.deno.dev"
NAVIGATION_API_URL = "/api/navigation/links"


def fetch_navigation_links():
    """
    获取 CursorX 导航链接

    Returns:
        dict: 包含导航链接的响应数据
    """
    url = f"{API_HOST}{NAVIGATION_API_URL}"

    print("=" * 70)
    print("CursorX 导航链接获取工具")
    print("=" * 70)
    print(f"\n[*] 请求 URL: {url}")

    try:
        # 发送 GET 请求
        response = requests.get(url, timeout=10)

        print(f"[*] HTTP 状态码: {response.status_code}")

        if response.status_code != 200:
            print(f"[!] 请求失败，状态码: {response.status_code}")
            return None

        # 解析 JSON 响应
        response_data = response.json()

        print(f"\n[*] 响应码: {response_data.get('code', 'N/A')}")
        print(f"[*] 响应消息: {response_data.get('message', 'N/A')}")

        return response_data

    except requests.exceptions.RequestException as e:
        print(f"\n[!] 请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"\n[!] JSON 解析失败: {e}")
        return None


def decode_navigation_data(response_data):
    """
    解码导航数据（支持双层 Base64 编码）

    Args:
        response_data: API 返回的响应数据

    Returns:
        tuple: (navigation_links, metadata) 导航链接列表和元数据
    """
    if not response_data:
        return None, None

    # 检查响应格式
    if 'data' not in response_data:
        print("[!] 响应中没有 data 字段")
        return None, None

    try:
        # 第一层：解码 data 字段
        data_encoded = response_data['data']
        print(f"\n[*] Data 字段长度: {len(data_encoded)} 字符")

        data_decoded = base64.b64decode(data_encoded).decode('utf-8')
        data_json = json.loads(data_decoded)

        print(f"[✓] 第一层解码成功")

        # 提取元数据
        ciphertext = data_json.get('ciphertext', '')
        timestamp = data_json.get('timestamp', 'N/A')
        nonce = data_json.get('nonce', 'N/A')

        print(f"[*] 时间戳: {timestamp}")
        print(f"[*] Nonce: {nonce}")
        print(f"[*] Ciphertext 长度: {len(ciphertext)} 字符")

        # 第二层：解码 ciphertext 字段
        ciphertext_decoded = base64.b64decode(ciphertext).decode('utf-8')
        print(f"[✓] 第二层解码成功")

        # 解析为 JSON
        navigation_links = json.loads(ciphertext_decoded)

        metadata = {
            'timestamp': timestamp,
            'nonce': nonce
        }

        return navigation_links, metadata

    except Exception as e:
        print(f"\n[!] 解码失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def display_navigation_links(links, metadata=None):
    """
    格式化显示导航链接

    Args:
        links: 导航链接列表
        metadata: 元数据（时间戳、nonce等）
    """
    if not links:
        print("\n[!] 没有可显示的导航链接")
        return

    print("\n" + "=" * 70)
    print("📋 导航链接列表")
    print("=" * 70)

    if metadata:
        print(f"\n⏰ 数据时间戳: {metadata.get('timestamp', 'N/A')}")
        print(f"🔑 Nonce: {metadata.get('nonce', 'N/A')}")

    for i, link in enumerate(links, 1):
        link_id = link.get('id', 'N/A')
        text = link.get('text', 'N/A')
        url = link.get('url', 'N/A')
        sort_order = link.get('sort_order', 'N/A')
        is_visible = link.get('is_visible', False)
        created_at = link.get('created_at', 'N/A')
        updated_at = link.get('updated_at', 'N/A')

        visibility = "✅ 可见" if is_visible else "❌ 隐藏"

        print(f"\n【链接 #{i}】(ID: {link_id})")
        print(f"  📝 文本: {text}")
        print(f"  🔗 URL: {url}")
        print(f"  📊 排序: {sort_order}")
        print(f"  👁️  状态: {visibility}")
        print(f"  📅 创建: {created_at}")
        print(f"  🔄 更新: {updated_at}")

    print("\n" + "=" * 70)


def save_to_file(links, metadata=None, filename="navigation_links.json"):
    """
    保存导航链接到文件

    Args:
        links: 导航链接列表
        metadata: 元数据
        filename: 保存的文件名
    """
    if not links:
        return

    try:
        output_data = {
            'metadata': metadata or {},
            'links': links,
            'fetched_at': datetime.now().isoformat()
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n[✓] 导航链接已保存到: {filename}")
    except Exception as e:
        print(f"\n[!] 保存文件失败: {e}")


def main():
    """主函数"""
    # 1. 获取导航链接
    response_data = fetch_navigation_links()

    if not response_data:
        print("\n[!] 无法获取导航链接")
        return

    # 2. 解码数据
    navigation_links, metadata = decode_navigation_data(response_data)

    if not navigation_links:
        print("\n[!] 无法解码导航数据")
        return

    # 3. 显示链接
    display_navigation_links(navigation_links, metadata)

    # 4. 保存到文件
    save_to_file(navigation_links, metadata)

    # 5. 生成统计信息
    print("\n📊 统计信息:")
    print(f"  总链接数: {len(navigation_links)}")
    visible_count = sum(1 for link in navigation_links if link.get('is_visible', False))
    print(f"  可见链接: {visible_count}")
    print(f"  隐藏链接: {len(navigation_links) - visible_count}")

    # 6. 显示可点击的链接
    print("\n🔗 可访问的链接:")
    for link in navigation_links:
        if link.get('is_visible', False):
            print(f"  • {link.get('text', 'N/A')}: {link.get('url', 'N/A')}")


if __name__ == "__main__":
    main()
