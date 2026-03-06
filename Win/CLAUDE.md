[根目录](../CLAUDE.md) > **Win**

---

# Win 模块 — CursorX.exe

> 最后更新：2026-03-06 12:36:16

---

## 变更记录 (Changelog)

| 版本 | 时间 | 说明 |
|------|------|------|
| v1.0 | 2026-03-06 | 初始化 Win 模块分析文档 |

---

## 模块职责

Win 模块是 CursorX v2.0 的 Windows 发行版本，以单一 PE32+ 可执行文件形式分发，无需安装器。其功能与 Mac 版本完全对称：

1. 通过 Wails v2 提供 GUI（WebView2 渲染 React 前端）
2. 调用服务端 API 验证并消耗"车票"
3. 定位并修改本地 Cursor 的 SQLite 认证数据库，注入伪造的企业级订阅凭证

---

## 文件结构

```
Win/
└── CursorX.exe    # PE32+ 单文件可执行，~9 MB，x86-64
```

Windows 版本无 Bundle 目录结构，所有资源（前端、图标、运行时）均嵌入 `.exe` 内部的 PE 节区。

---

## PE32+ 结构说明

### 基本信息

| 项目 | 值 |
|------|----|
| 文件格式 | PE32+ (64-bit) |
| 目标架构 | x86-64 (AMD64) |
| 文件大小 | ~9 MB（大于 Mac 版 ~7 MB，因缺少 Universal Binary 双份 slice 但含 Windows 运行时） |
| 入口点 | Go 运行时 bootstrap（`_rt0_amd64_windows`） |
| 嵌入前端 | `.rsrc` 节区或 Go embed 数据节区 |

### PE 节区结构（预期）

```
节区名      用途
─────────────────────────────────────────────
.text       代码段（Go 编译后的机器码）
.rdata      只读数据（字符串常量、函数名、AES 密钥等）
.data       可写数据（全局变量）
.bss        未初始化数据
.rsrc       Windows 资源（图标、版本信息）
.pdata      异常处理表（x64 标准）
```

查看节区：

```bash
python3 -c "
import pefile
pe = pefile.PE('Win/CursorX.exe')
for s in pe.sections:
    name = s.Name.decode(errors='replace').strip('\x00')
    print(f'{name:<10} VA=0x{s.VirtualAddress:08x}  Size={s.SizeOfRawData//1024}KB')
"
```

### 定位嵌入前端资源

```bash
# 搜索 React/webpack 特征字符串
python3 -c "
data = open('Win/CursorX.exe','rb').read()
for sig in [b'React', b'useState', b'__wails', b'webpack']:
    idx = data.find(sig)
    if idx > 0:
        print(f'{sig.decode()}: offset {idx} (0x{idx:x})')
"
```

---

## 与 Mac 版本的差异点

| 维度 | Mac 版本 | Win 版本 |
|------|---------|---------|
| 发行格式 | `.app` Bundle | 单文件 `.exe` |
| 二进制格式 | Mach-O Universal | PE32+ x86-64 |
| 架构支持 | x86_64 + arm64 双架构 | 仅 x86-64 |
| 文件大小 | ~7 MB | ~9 MB |
| WebView 实现 | WKWebView（系统原生） | WebView2（需 Edge 运行时） |
| 数据库路径变量 | `$HOME` | `%APPDATA%` |
| 数据库路径 | `~/Library/Application Support/Cursor/...` | `%APPDATA%\Cursor\...` |
| Bundle 配置 | Info.plist | PE `.rsrc` 节版本信息 |
| 代码签名 | macOS Gatekeeper 机制 | Authenticode（预计未签名或自签） |
| Go 编译目标 | `GOOS=darwin` | `GOOS=windows` |
| CGO 支持 | 启用（go-sqlite3 需要） | 启用（需 MinGW 交叉编译） |

**核心逻辑完全相同**：API 调用、AES 加密、数据库写入逻辑由同一套 Go 源码编译而来，仅平台相关的路径处理和 WebView 适配层不同。

---

## 目标数据库

| 项目 | 值 |
|------|----|
| 路径 | `%APPDATA%\Cursor\User\globalStorage\state.vscdb` |
| 典型绝对路径示例 | `C:\Users\{用户名}\AppData\Roaming\Cursor\User\globalStorage\state.vscdb` |
| 格式 | SQLite 3 |
| 操作方式 | `go-sqlite3` CGO 绑定 |
| 写入函数 | `main.(*CursorAuthManager).UpdateCursorAuthValue` |

写入字段与 Mac 版本完全一致：

```
cursorAuth/accessToken          → 服务端返回的 access token
cursorAuth/refreshToken         → 服务端返回的 refresh token
cursorAuth/stripeMembershipType → "enterprise"
cursorAuth/cachedEmail          → 关联邮箱
```

---

## API 通信

与 Mac 版本使用完全相同的 API 配置：

```
Host:    https://cursorxpro.deno.dev
端点1:   POST /api/tickets/use
端点2:   GET  /api/navigation/links
加密:    AES (CryptoJS 兼容)
密钥:    nKEg32K9jsdJRMSA2pcn83LM9sUUwq29
```

---

## 分析要点与建议

### 已确认信息
- [x] PE32+ x86-64 格式
- [x] 与 Mac 版本功能对称，同套 Go 源码
- [x] AES 硬编码密钥（同 Mac 版本）
- [x] API 端点与数据库路径

### 待深入分析
- [ ] PE 版本信息节区（`FileVersion`、`ProductName` 等 `.rsrc` 字段）
- [ ] 是否有 Authenticode 签名（`signtool verify /v CursorX.exe`）
- [ ] 前端 JS 提取（偏移位置需独立定位，与 Mac 不同）
- [ ] 导入表分析 — 确认 Windows API 调用（`CreateFile`、`RegOpenKey` 等）
- [ ] WebView2 初始化参数 — 确认是否使用持久化用户数据目录
- [ ] 防调试检测 — 是否调用 `IsDebuggerPresent`（strings/imports 检查）

### 快速分析命令集

```bash
# 1. 确认文件类型
file Win/CursorX.exe
xxd Win/CursorX.exe | head -4   # 应看到 4d 5a (MZ 魔数)

# 2. 提取所有字符串
strings Win/CursorX.exe | grep -Ei \
  "cursor|ticket|auth|token|stripe|enterprise|api|http|sqlite|machine" \
  > /tmp/cursorx_win_strings.txt
wc -l /tmp/cursorx_win_strings.txt

# 3. 定位关键字符串偏移
python3 -c "
data = open('Win/CursorX.exe','rb').read()
targets = {
    'AES Key':  b'nKEg32K9jsdJRMSA2pcn83LM9sUUwq29',
    'API Host': b'cursorxpro.deno.dev',
    'DB Path':  b'globalStorage',
    'Field':    b'stripeMembershipType',
}
for label, pattern in targets.items():
    idx = data.find(pattern)
    status = f'0x{idx:x}' if idx >= 0 else 'NOT FOUND'
    print(f'{label:<25} {status}')
"

# 4. PE 结构分析（需安装 pefile）
python3 -c "
import pefile
pe = pefile.PE('Win/CursorX.exe')
print('Machine:', hex(pe.FILE_HEADER.Machine))
print('TimeDateStamp:', pe.FILE_HEADER.TimeDateStamp)
print('Sections:')
for s in pe.sections:
    print(' ', s.Name.decode(errors='replace').strip(), hex(s.VirtualAddress), s.SizeOfRawData)
if hasattr(pe, 'VS_VERSIONINFO'):
    print('Has version info')
"

# 5. 检查导入表中的可疑 API
python3 -c "
import pefile
pe = pefile.PE('Win/CursorX.exe')
if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
    for imp in pe.DIRECTORY_ENTRY_IMPORT:
        dll = imp.dll.decode(errors='replace')
        for func in imp.imports:
            if func.name:
                name = func.name.decode(errors='replace')
                if any(k in name.lower() for k in ['debug','reg','crypt','sqlite']):
                    print(f'{dll} -> {name}')
"

# 6. 动态分析（x64dbg / WinDbg）
# 在以下函数处下断点（通过符号或模式匹配定位）：
# main.(*App).UpdateCursorAuth
# main.encryptRequest
# main.(*CursorAuthManager).UpdateCursorAuthValue
```

---

## 相关文件清单

| 文件 | 绝对路径 | 重要性 |
|------|----------|--------|
| 主可执行文件 | `Win/CursorX.exe` | 最高 - 所有逻辑均在此文件内 |
