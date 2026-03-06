#!/usr/bin/env python3
"""
CursorX 激活请求构造工具
用于生成和发送 CursorX 车票激活请求
"""

import json
import hashlib
import base64
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import platform
import sys

# CursorX 配置
API_HOST = "https://cursorxpro.deno.dev"
TICKET_API_URL = "/api/tickets/use"
AES_KEY = "nKEg32K9jsdJRMSA2pcn83LM9sUUwq29"


def generate_machine_code():
    """
    生成机器指纹（简化版）
    实际应用中应该收集更多硬件信息
    """
    # 获取系统信息
    system = platform.system()
    machine = platform.machine()
    processor = platform.processor()

    # 构造指纹字符串
    fingerprint = f"{system}|{machine}|{processor}"

    # SHA-256 哈希
    hash_obj = hashlib.sha256(fingerprint.encode('utf-8'))
    return hash_obj.hexdigest()


def detect_platform():
    """检测操作系统平台"""
    system = platform.system().lower()
    if 'darwin' in system:
        return "MAC"
    elif 'windows' in system:
        return "WINDOWS"
    elif 'linux' in system:
        return "LINUX"
    else:
        return "OTHER"


def aes_encrypt(data, key):
    """
    AES-256-CBC 加密
    使用 PKCS7 填充，返回 Base64 编码
    """
    # 将密钥转换为字节
    key_bytes = key.encode('utf-8')

    # 将数据转换为 JSON 字符串
    if isinstance(data, dict):
        data = json.dumps(data, separators=(',', ':'))

    data_bytes = data.encode('utf-8')

    # 创建 AES 加密器（CBC 模式）
    # IV 使用密钥的前 16 字节（与 CryptoJS 默认行为一致）
    iv = key_bytes[:16]
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)

    # 填充并加密
    padded_data = pad(data_bytes, AES.block_size)
    encrypted = cipher.encrypt(padded_data)

    # Base64 编码
    return base64.b64encode(encrypted).decode('utf-8')


def aes_decrypt(encrypted_data, key):
    """
    AES-256-CBC 解密
    输入 Base64 编码的密文，返回解密后的字典
    """
    # 将密钥转换为字节
    key_bytes = key.encode('utf-8')

    # Base64 解码
    encrypted_bytes = base64.b64decode(encrypted_data)

    # 创建 AES 解密器
    iv = key_bytes[:16]
    cipher = AES.new(key_bytes, AES.MODE_CBC, iv)

    # 解密并去除填充
    decrypted = cipher.decrypt(encrypted_bytes)
    unpadded = unpad(decrypted, AES.block_size)

    # 解析 JSON
    return json.loads(unpadded.decode('utf-8'))


def construct_request(ticket_code, machine_code=None, platform_type=None):
    """
    构造激活请求

    Args:
        ticket_code: 车票码（如 "NQXS14YS"）
        machine_code: 机器指纹（可选，自动生成）
        platform_type: 平台类型（可选，自动检测）

    Returns:
        dict: 包含加密请求体的字典
    """
    # 自动生成机器码
    if machine_code is None:
        machine_code = generate_machine_code()

    # 自动检测平台
    if platform_type is None:
        platform_type = detect_platform()

    # 构造请求数据
    request_data = {
        "ticketCode": ticket_code,
        "machineCode": machine_code,
        "platform": platform_type
    }

    print(f"\n[*] 原始请求数据:")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))

    # AES 加密
    encrypted = aes_encrypt(request_data, AES_KEY)

    print(f"\n[*] 加密后的数据 (前100字符):")
    print(encrypted[:100] + "...")

    # 构造最终请求体
    final_request = {
        "data": encrypted
    }

    return final_request, request_data


def send_request(ticket_code, machine_code=None, platform_type=None):
    """
    发送激活请求到 CursorX 服务器

    Args:
        ticket_code: 车票码
        machine_code: 机器指纹（可选）
        platform_type: 平台类型（可选）

    Returns:
        dict: 服务器响应
    """
    # 构造请求
    request_body, original_data = construct_request(ticket_code, machine_code, platform_type)

    # 发送请求
    url = f"{API_HOST}{TICKET_API_URL}"
    headers = {
        "Content-Type": "application/json"
    }

    print(f"\n[*] 发送请求到: {url}")
    print(f"[*] 机器码: {original_data['machineCode']}")
    print(f"[*] 平台: {original_data['platform']}")

    try:
        response = requests.post(url, json=request_body, headers=headers, timeout=10)

        print(f"\n[*] HTTP 状态码: {response.status_code}")

        # 解析响应
        response_data = response.json()
        print(f"\n[*] 服务器响应:")
        print(json.dumps(response_data, indent=2, ensure_ascii=False))

        # 如果成功，解密 data 字段
        if response_data.get('code') == 200 and response_data.get('data'):
            try:
                decrypted_data = aes_decrypt(response_data['data'], AES_KEY)
                print(f"\n[*] 解密后的数据:")
                print(json.dumps(decrypted_data, indent=2, ensure_ascii=False))

                return {
                    'success': True,
                    'response': response_data,
                    'decrypted': decrypted_data
                }
            except Exception as e:
                print(f"\n[!] 解密失败: {e}")
                return {
                    'success': False,
                    'response': response_data,
                    'error': str(e)
                }
        else:
            return {
                'success': False,
                'response': response_data
            }

    except requests.exceptions.RequestException as e:
        print(f"\n[!] 请求失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """主函数"""
    print("=" * 60)
    print("CursorX 激活请求构造工具")
    print("=" * 60)

    # 从命令行参数获取车票码
    if len(sys.argv) > 1:
        ticket_code = sys.argv[1]
    else:
        ticket_code = input("\n请输入车票码: ").strip()

    if not ticket_code:
        print("[!] 车票码不能为空")
        sys.exit(1)

    # 询问是否发送请求
    print(f"\n[?] 是否发送请求到服务器? (y/n): ", end="")
    choice = input().strip().lower()

    if choice == 'y':
        result = send_request(ticket_code)

        if result.get('success'):
            print("\n" + "=" * 60)
            print("✅ 激活成功!")
            print("=" * 60)
            decrypted = result.get('decrypted', {})
            print(f"Token: {decrypted.get('token', 'N/A')}")
            print(f"ID: {decrypted.get('id', 'N/A')}")
        else:
            print("\n" + "=" * 60)
            print("❌ 激活失败")
            print("=" * 60)
    else:
        # 仅构造请求，不发送
        request_body, original_data = construct_request(ticket_code)
        print(f"\n[*] 完整请求体:")
        print(json.dumps(request_body, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
