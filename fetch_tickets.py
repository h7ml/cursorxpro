#!/usr/bin/env python3
"""
CursorX 票据管理工具（完整版）
用于验证、使用和查询 CursorX 车票
支持真正的 AES 加密（需要 cryptography 库）
"""

import json
import base64
import hashlib
import platform
import requests
from datetime import datetime
import sys

# CursorX 配置
API_HOST = "https://cursorxpro.deno.dev"
TICKET_USE_URL = "/api/tickets/use"
AES_KEY = "nKEg32K9jsdJRMSA2pcn83LM9sUUwq29"

# 尝试导入加密库
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def pad_pkcs7(data):
    """PKCS7 填充"""
    padding_length = 16 - (len(data) % 16)
    padding = bytes([padding_length] * padding_length)
    return data + padding


def unpad_pkcs7(data):
    """PKCS7 去填充"""
    padding_length = data[-1]
    return data[:-padding_length]


def aes_encrypt(data, key):
    """
    AES-256-CBC 加密

    Args:
        data: 要加密的数据（字典或字符串）
        key: AES 密钥字符串

    Returns:
        Base64 编码的密文
    """
    if not HAS_CRYPTO:
        print("[!] 警告: 未安装 cryptography 库，使用简化加密")
        print("[!] 安装命令: pip3 install cryptography")
        # 简化版本：仅 Base64 编码
        if isinstance(data, dict):
            data = json.dumps(data, separators=(',', ':'))
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')

    # 将数据转换为 JSON 字符串
    if isinstance(data, dict):
        data = json.dumps(data, separators=(',', ':'))

    data_bytes = data.encode('utf-8')
    key_bytes = key.encode('utf-8')

    # 使用密钥的前 16 字节作为 IV（与 CryptoJS 默认行为一致）
    iv = key_bytes[:16]

    # 创建 AES 加密器
    cipher = Cipher(
        algorithms.AES(key_bytes),
        modes.CBC(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()

    # 填充并加密
    padded_data = pad_pkcs7(data_bytes)
    encrypted = encryptor.update(padded_data) + encryptor.finalize()

    # Base64 编码
    return base64.b64encode(encrypted).decode('utf-8')


def aes_decrypt(encrypted_data, key):
    """
    AES-256-CBC 解密

    Args:
        encrypted_data: Base64 编码的密文
        key: AES 密钥字符串

    Returns:
        解密后的字典或字符串
    """
    if not HAS_CRYPTO:
        # 简化版本：仅 Base64 解码
        try:
            decoded = base64.b64decode(encrypted_data).decode('utf-8')
            return json.loads(decoded)
        except:
            return None

    key_bytes = key.encode('utf-8')
    encrypted_bytes = base64.b64decode(encrypted_data)

    # 使用密钥的前 16 字节作为 IV
    iv = key_bytes[:16]

    # 创建 AES 解密器
    cipher = Cipher(
        algorithms.AES(key_bytes),
        modes.CBC(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()

    # 解密并去除填充
    decrypted = decryptor.update(encrypted_bytes) + decryptor.finalize()
    unpadded = unpad_pkcs7(decrypted)

    # 解析 JSON
    try:
        return json.loads(unpadded.decode('utf-8'))
    except:
        return unpadded.decode('utf-8')


def generate_machine_code():
    """
    生成机器指纹
    """
    system = platform.system()
    machine = platform.machine()
    processor = platform.processor()

    fingerprint = f"{system}|{machine}|{processor}"
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


def use_ticket(ticket_code, machine_code=None, platform_type=None, verbose=True):
    """
    使用车票进行激活

    Args:
        ticket_code: 车票码
        machine_code: 机器指纹（可选）
        platform_type: 平台类型（可选）
        verbose: 是否显示详细信息

    Returns:
        dict: 激活结果
    """
    # 自动生成机器码
    if machine_code is None:
        machine_code = generate_machine_code()

    # 自动检测平台
    if platform_type is None:
        platform_type = detect_platform()

    if verbose:
        print("=" * 70)
        print("CursorX 车票使用工具")
        print("=" * 70)
        print(f"\n[*] 车票码: {ticket_code}")
        print(f"[*] 机器码: {machine_code[:32]}...")
        print(f"[*] 平台: {platform_type}")
        print(f"[*] 加密库: {'✅ cryptography' if HAS_CRYPTO else '❌ 简化模式'}")

    # 构造请求数据
    request_data = {
        "ticketCode": ticket_code,
        "machineCode": machine_code,
        "platform": platform_type
    }

    # AES 加密
    encrypted = aes_encrypt(request_data, AES_KEY)

    request_body = {
        "data": encrypted
    }

    # 发送请求
    url = f"{API_HOST}{TICKET_USE_URL}"
    headers = {
        "Content-Type": "application/json"
    }

    if verbose:
        print(f"\n[*] 发送请求到: {url}")

    try:
        response = requests.post(url, json=request_body, headers=headers, timeout=10)

        if verbose:
            print(f"[*] HTTP 状态码: {response.status_code}")

        # 解析响应
        response_data = response.json()

        if verbose:
            print(f"\n[*] 响应码: {response_data.get('code', 'N/A')}")
            print(f"[*] 响应消息: {response_data.get('message', 'N/A')}")

        # 如果成功，尝试解密 data 字段
        if response_data.get('code') == 200 and response_data.get('data'):
            if verbose:
                print(f"\n[*] 尝试解密响应数据...")

            decrypted = aes_decrypt(response_data['data'], AES_KEY)

            if decrypted:
                if verbose:
                    print(f"\n[✓] 激活成功!")
                    print(f"\n解密后的数据:")
                    print(json.dumps(decrypted, indent=2, ensure_ascii=False))

                return {
                    'success': True,
                    'response': response_data,
                    'decrypted': decrypted,
                    'ticket_code': ticket_code,
                    'machine_code': machine_code,
                    'platform': platform_type
                }
            else:
                if verbose:
                    print(f"\n[!] 解密失败")
                return {
                    'success': False,
                    'response': response_data,
                    'error': '解密失败'
                }
        else:
            if verbose:
                print(f"\n[✗] 激活失败")
            return {
                'success': False,
                'response': response_data,
                'ticket_code': ticket_code
            }

    except requests.exceptions.RequestException as e:
        if verbose:
            print(f"\n[!] 请求失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'ticket_code': ticket_code
        }


def validate_ticket_format(ticket_code):
    """
    验证车票码格式

    Args:
        ticket_code: 车票码

    Returns:
        tuple: (是否有效, 消息)
    """
    if not ticket_code:
        return False, "车票码不能为空"

    ticket_code = ticket_code.strip()

    if len(ticket_code) < 6:
        return False, "车票码长度不足"

    if not ticket_code.replace('-', '').replace('_', '').isalnum():
        return False, "车票码包含非法字符"

    return True, "格式有效"


def display_ticket_info(ticket_code):
    """显示车票信息"""
    print("=" * 70)
    print("车票信息")
    print("=" * 70)

    is_valid, message = validate_ticket_format(ticket_code)

    print(f"\n车票码: {ticket_code}")
    print(f"格式验证: {'✅ ' + message if is_valid else '❌ ' + message}")
    print(f"长度: {len(ticket_code)} 字符")

    if is_valid:
        print(f"\n[*] 该车票码格式有效，可以尝试使用")
    else:
        print(f"\n[!] 该车票码格式无效，请检查")


def save_ticket_result(result, filename="ticket_result.json"):
    """保存车票使用结果到文件"""
    try:
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'result': result
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n[✓] 结果已保存到: {filename}")
    except Exception as e:
        print(f"\n[!] 保存文件失败: {e}")


def batch_test_tickets(ticket_codes):
    """
    批量测试多个车票

    Args:
        ticket_codes: 车票码列表
    """
    print("=" * 70)
    print("批量测试车票")
    print("=" * 70)
    print(f"\n总数: {len(ticket_codes)} 个车票\n")

    results = []

    for i, ticket_code in enumerate(ticket_codes, 1):
        print(f"\n[{i}/{len(ticket_codes)}] 测试车票: {ticket_code}")
        print("-" * 70)

        result = use_ticket(ticket_code, verbose=False)
        results.append(result)

        if result.get('success'):
            print(f"✅ 成功")
        else:
            print(f"❌ 失败: {result.get('response', {}).get('message', result.get('error', '未知错误'))}")

    # 统计
    success_count = sum(1 for r in results if r.get('success'))
    print(f"\n" + "=" * 70)
    print(f"测试完成: {success_count}/{len(ticket_codes)} 成功")
    print("=" * 70)

    return results


def main():
    """主函数"""
    print("=" * 70)
    print("CursorX 票据管理工具")
    print("=" * 70)
    print("\n功能:")
    print("  1. 验证车票格式")
    print("  2. 使用车票激活")
    print("  3. 查看机器码")
    print("  4. 批量测试车票")
    print("\n" + "=" * 70)

    # 从命令行参数获取车票码
    if len(sys.argv) > 1:
        ticket_code = sys.argv[1]
    else:
        ticket_code = input("\n请输入车票码 (或输入 'info' 查看机器码): ").strip()

    # 特殊命令
    if ticket_code.lower() == 'info':
        machine_code = generate_machine_code()
        platform_type = detect_platform()
        print(f"\n当前机器信息:")
        print(f"  机器码: {machine_code}")
        print(f"  平台: {platform_type}")
        print(f"  加密库: {'✅ 已安装' if HAS_CRYPTO else '❌ 未安装 (pip3 install cryptography)'}")
        return

    if not ticket_code:
        print("[!] 车票码不能为空")
        sys.exit(1)

    # 验证格式
    is_valid, message = validate_ticket_format(ticket_code)
    if not is_valid:
        print(f"\n[!] {message}")
        display_ticket_info(ticket_code)
        sys.exit(1)

    # 询问是否使用车票
    print(f"\n[?] 是否使用车票 '{ticket_code}' 进行激活? (y/n): ", end="")
    choice = input().strip().lower()

    if choice == 'y':
        result = use_ticket(ticket_code)

        # 保存结果
        save_ticket_result(result)

        if result.get('success'):
            print("\n" + "=" * 70)
            print("✅ 激活成功!")
            print("=" * 70)

            decrypted = result.get('decrypted', {})
            if decrypted:
                token = decrypted.get('token', 'N/A')
                print(f"\nToken: {token[:50]}..." if len(token) > 50 else f"\nToken: {token}")
                print(f"ID: {decrypted.get('id', 'N/A')}")
                print(f"\n[*] 请重启 Cursor IDE 以生效")
        else:
            print("\n" + "=" * 70)
            print("❌ 激活失败")
            print("=" * 70)
            error = result.get('error')
            if error:
                print(f"错误: {error}")
    else:
        print("\n[*] 已取消")
        display_ticket_info(ticket_code)


if __name__ == "__main__":
    main()
