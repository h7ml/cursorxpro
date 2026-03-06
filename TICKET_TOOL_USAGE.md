# CursorX 票据管理工具使用说明

## 概述

`fetch_tickets.py` 是一个用于管理和使用 CursorX 车票的命令行工具。

## 功能特性

1. ✅ **车票格式验证** - 检查车票码是否符合格式要求
2. ✅ **车票激活** - 使用车票码进行 Cursor IDE 激活
3. ✅ **机器信息查看** - 显示当前机器的指纹和平台信息
4. ✅ **批量测试** - 支持批量测试多个车票码
5. ✅ **AES 加密** - 支持真正的 AES-256-CBC 加密（需要 cryptography 库）
6. ✅ **结果保存** - 自动保存激活结果到 JSON 文件

## 安装依赖

```bash
# 安装必需的库
pip3 install requests

# 安装加密库（推荐，用于真正的 AES 加密）
pip3 install cryptography
```

## 使用方法

### 1. 查看机器信息

```bash
python3 fetch_tickets.py info
```

输出示例：
```
当前机器信息:
  机器码: a56ced4e148a825b5f243aae9aadb7772d19c7773babdae59ecb68ef6ba076e1
  平台: MAC
  加密库: ✅ 已安装
```

### 2. 使用车票激活

#### 交互式模式

```bash
python3 fetch_tickets.py
```

然后按提示输入车票码。

#### 命令行模式

```bash
python3 fetch_tickets.py NQXS14YS
```

### 3. 激活流程

```
======================================================================
CursorX 车票使用工具
======================================================================

[*] 车票码: NQXS14YS
[*] 机器码: a56ced4e148a825b5f243aae9aadb7772d19c7773babdae59ecb68ef6ba076e1
[*] 平台: MAC
[*] 加密库: ✅ cryptography

[*] 发送请求到: https://cursorxpro.deno.dev/api/tickets/use
[*] HTTP 状态码: 200

[*] 响应码: 200
[*] 响应消息: 激活成功

[*] 尝试解密响应数据...

[✓] 激活成功!

解密后的数据:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "id": "usr_abc123def456"
}

[✓] 结果已保存到: ticket_result.json

======================================================================
✅ 激活成功!
======================================================================

Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
ID: usr_abc123def456

[*] 请重启 Cursor IDE 以生效
```

## 工作原理

### 1. 机器指纹生成

```python
fingerprint = f"{system}|{machine}|{processor}"
machine_code = SHA256(fingerprint)
```

示例：
- 输入：`Darwin|arm64|arm`
- 输出：`a56ced4e148a825b5f243aae9aadb7772d19c7773babdae59ecb68ef6ba076e1`

### 2. 请求构造

```json
{
  "ticketCode": "NQXS14YS",
  "machineCode": "a56ced4e...",
  "platform": "MAC"
}
```

### 3. AES 加密

- **算法**：AES-256-CBC
- **密钥**：`nKEg32K9jsdJRMSA2pcn83LM9sUUwq29`
- **IV**：密钥的前 16 字节
- **填充**：PKCS7
- **输出**：Base64 编码

### 4. 发送请求

```http
POST https://cursorxpro.deno.dev/api/tickets/use
Content-Type: application/json

{
  "data": "<Base64 编码的 AES 加密数据>"
}
```

### 5. 响应处理

成功响应：
```json
{
  "code": 200,
  "message": "激活成功",
  "data": "<Base64 编码的 AES 加密数据>"
}
```

解密后：
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "id": "usr_abc123def456"
}
```

## 错误处理

### 常见错误

| 错误码 | 消息 | 原因 |
|--------|------|------|
| 400 | 车票无效或已使用 | 车票码不存在或已被使用 |
| 403 | 车票已过期 | 车票超过有效期 |
| 409 | 该车票已绑定其他设备 | 车票已在其他机器上激活 |
| 500 | 服务器错误 | 服务端异常 |

### 调试模式

如果遇到问题，可以查看详细的请求和响应信息：

```python
# 在脚本中启用详细输出
result = use_ticket(ticket_code, verbose=True)
```

## 输出文件

### ticket_result.json

激活结果会自动保存到此文件：

```json
{
  "timestamp": "2026-03-06T13:10:00.123456",
  "result": {
    "success": true,
    "response": {
      "code": 200,
      "message": "激活成功",
      "data": "..."
    },
    "decrypted": {
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "id": "usr_abc123def456"
    },
    "ticket_code": "NQXS14YS",
    "machine_code": "a56ced4e...",
    "platform": "MAC"
  }
}
```

## 高级用法

### 批量测试车票

```python
from fetch_tickets import batch_test_tickets

tickets = ["TICKET1", "TICKET2", "TICKET3"]
results = batch_test_tickets(tickets)
```

### 自定义机器码

```python
from fetch_tickets import use_ticket

result = use_ticket(
    ticket_code="NQXS14YS",
    machine_code="custom_machine_code_here",
    platform_type="MAC"
)
```

## 安全注意事项

⚠️ **重要提示**：

1. **AES 密钥硬编码** - 密钥 `nKEg32K9jsdJRMSA2pcn83LM9sUUwq29` 是硬编码在客户端的，任何人都可以提取
2. **机器指纹简单** - 当前的机器指纹生成算法较简单，可能被伪造
3. **无签名验证** - 请求和响应没有数字签名，可能被中间人攻击
4. **明文传输元数据** - 虽然数据加密，但 HTTP 头和元数据是明文的

## 故障排除

### 问题：加密库未安装

```
[!] 警告: 未安装 cryptography 库，使用简化加密
[!] 安装命令: pip3 install cryptography
```

**解决方案**：
```bash
pip3 install cryptography
```

### 问题：请求超时

```
[!] 请求失败: HTTPSConnectionPool(host='cursorxpro.deno.dev', port=443): Read timed out.
```

**解决方案**：
- 检查网络连接
- 检查防火墙设置
- 尝试使用代理

### 问题：车票格式无效

```
[!] 车票码包含非法字符
```

**解决方案**：
- 检查车票码是否正确复制
- 确保没有多余的空格或特殊字符
- 车票码应该只包含字母、数字、连字符和下划线

## 相关文件

- `fetch_navigation.py` - 导航链接获取工具
- `construct_request.py` - 请求构造工具
- `API_REQUEST_EXAMPLE.md` - API 请求示例文档
- `CLAUDE.md` - 项目总览文档

## 许可声明

⚠️ 本工具仅用于**安全研究和教育目的**。使用本工具激活 Cursor IDE 可能违反其服务条款。
