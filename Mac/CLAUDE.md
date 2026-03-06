[根目录](../CLAUDE.md) > **Mac**

---

# Mac 模块 — CursorX.app

> 最后更新：2026-03-06 12:36:16

---

## 变更记录 (Changelog)

| 版本 | 时间 | 说明 |
|------|------|------|
| v1.0 | 2026-03-06 | 初始化 Mac 模块分析文档 |

---

## 模块职责

Mac 模块是 CursorX v2.0 的 macOS 发行版本，打包为标准 `.app` Bundle 格式。其核心职责为：

1. 通过 Wails v2 提供跨平台 GUI（WebView 渲染 React 前端）
2. 调用服务端 API 验证并消耗"车票"
3. 定位并修改本地 Cursor 的 SQLite 认证数据库，注入伪造的企业级订阅凭证

---

## 文件结构

```
Mac/
└── CursorX.app/
    └── Contents/
        ├── Info.plist          # Apple Bundle 元数据，Bundle ID: com.wails.CursorX
        ├── MacOS/
        │   └── CursorX         # 主可执行文件，Universal Binary
        └── Resources/
            └── iconfile.icns   # 应用图标（Apple ICNS 格式）
```

### 各文件说明

| 文件 | 类型 | 说明 |
|------|------|------|
| `Info.plist` | XML Property List | Bundle 元数据，含 Bundle ID、版本、最低系统要求 |
| `MacOS/CursorX` | Mach-O Universal Binary | 核心逻辑，含 x86_64 和 arm64 双架构 slice |
| `Resources/iconfile.icns` | ICNS 图标 | 应用图标，不含逻辑，可忽略 |

---

## Info.plist 关键字段

```xml
CFBundleIdentifier    = com.wails.CursorX
CFBundleName          = CursorX
CFBundleVersion       = 2.0.0
CFBundleGetInfoString = CursorX车票验证应用      <!-- 明确表明用途 -->
LSMinimumSystemVersion = 10.13.0               <!-- 最低 macOS High Sierra -->
NSHighResolutionCapable = true                 <!-- Retina 支持 -->
NSHumanReadableCopyright = Copyright 2025
```

---

## 架构细节

### Universal Binary 结构

```
CursorX (Mach-O Universal Binary)
├── Slice 0: x86_64 (Intel Mac)
│   ├── Mach-O 64-bit executable
│   └── 包含完整 Go 运行时 + Wails 运行时 + 嵌入前端资源
└── Slice 1: arm64 (Apple Silicon)
    ├── Mach-O 64-bit executable
    └── 包含完整 Go 运行时 + Wails 运行时 + 嵌入前端资源
```

用 `lipo` 可分离两个 slice：

```bash
lipo -thin x86_64 Mac/CursorX.app/Contents/MacOS/CursorX -output CursorX_x86_64
lipo -thin arm64  Mac/CursorX.app/Contents/MacOS/CursorX -output CursorX_arm64
```

### Wails v2 框架层次

```
┌─────────────────────────────────────┐
│           macOS WebView             │  ← WKWebView (系统原生)
│         React 18 前端               │  ← 嵌入在二进制内部
│   (HTML + JS + CSS, ~偏移5.6MB处)   │
├─────────────────────────────────────┤
│         Wails v2 运行时桥接          │  ← Go ↔ JS 双向通信
├─────────────────────────────────────┤
│           Go 后端逻辑               │
│  main.(*App)                        │
│  main.(*CursorAuthManager)          │
│  main.encryptRequest                │
│  main.decryptResponse               │
├─────────────────────────────────────┤
│         Go 标准库 + CGO             │
│  go-sqlite3 (CGO)                   │
│  machineid                          │
│  google/uuid                        │
└─────────────────────────────────────┘
```

### 嵌入前端资源位置

Wails v2 使用 Go `embed` 机制将前端构建产物（`dist/`）直接嵌入二进制。

- 前端 JS 代码位于文件偏移约 `~5.6 MB` 处
- 可使用以下方法提取：

```bash
# 搜索 JS 特征头（webpack bundle 通常以 !function 或 (()=> 开头）
python3 -c "
data = open('Mac/CursorX.app/Contents/MacOS/CursorX','rb').read()
# 搜索常见 React/webpack bundle 特征
for sig in [b'React', b'useState', b'webpack', b'__wails']:
    idx = data.find(sig)
    if idx > 0:
        print(f'{sig}: offset {idx} (0x{idx:x})')
"

# 按大致偏移范围转储
dd if=Mac/CursorX.app/Contents/MacOS/CursorX bs=1 skip=5800000 count=200000 \
   | strings | head -100
```

---

## 关键偏移信息

| 特征 | 估算偏移 | 备注 |
|------|----------|------|
| 嵌入前端 JS 代码起始 | ~0x570000 (~5.6 MB) | Wails embed 资源区 |
| AES 密钥字符串 | 待定位 | `nKEg32K9jsdJRMSA2pcn83LM9sUUwq29` |
| API Host 字符串 | 待定位 | `cursorxpro.deno.dev` |
| Go 符号表 | 二进制内部 | `go tool nm` 可枚举 |

定位 AES 密钥精确偏移：

```bash
python3 -c "
data = open('Mac/CursorX.app/Contents/MacOS/CursorX','rb').read()
key  = b'nKEg32K9jsdJRMSA2pcn83LM9sUUwq29'
host = b'cursorxpro.deno.dev'
for label, pattern in [('AES Key', key), ('API Host', host)]:
    idx = data.find(pattern)
    print(f'{label}: offset {idx} (0x{idx:x})')
"
```

---

## 目标数据库

| 项目 | 值 |
|------|----|
| 路径 | `$HOME/Library/Application Support/Cursor/User/globalStorage/state.vscdb` |
| 格式 | SQLite 3 |
| 操作方式 | `go-sqlite3` CGO 绑定，直接 UPDATE |
| 写入函数 | `main.(*CursorAuthManager).UpdateCursorAuthValue` |

写入的字段（键名 → 写入值）：

```
cursorAuth/accessToken          → 服务端返回的 access token
cursorAuth/refreshToken         → 服务端返回的 refresh token
cursorAuth/stripeMembershipType → "enterprise"（硬编码）
cursorAuth/cachedEmail          → 关联邮箱
```

---

## API 通信流程

```
[React 前端] 用户输入车票号
     │
     ▼ Wails Bridge 调用 Go
[main.(*App).UpdateCursorAuth]
     │
     ├─► [main.encryptRequest] AES 加密请求体
     │         密钥: nKEg32K9jsdJRMSA2pcn83LM9sUUwq29
     │
     ├─► POST https://cursorxpro.deno.dev/api/tickets/use
     │         请求体: 加密后的车票信息 + machineid
     │
     ├─► [main.decryptResponse] AES 解密响应
     │
     └─► [main.(*CursorAuthManager).UpdateCursorAuthValue]
               写入 state.vscdb 四个字段
```

---

## 分析要点与建议

### 已确认信息
- [x] Bundle ID 和版本号（来自 Info.plist）
- [x] Universal Binary 双架构（x86_64 + arm64）
- [x] Wails v2 框架 + React 18 前端
- [x] AES 硬编码密钥
- [x] API 端点与数据库路径
- [x] 关键 Go 函数名

### 待深入分析
- [ ] 前端 JS 代码完整提取（`~5.6 MB` 偏移处）— 可还原 UI 交互逻辑和车票请求结构
- [ ] `machineid` 具体算法 — 确认设备指纹收集范围（IOPlatformSerialNumber 等）
- [ ] `POST /api/tickets/use` 完整请求/响应 schema — 需动态抓包或解密静态字符串
- [ ] 符号表完整枚举 — `go tool nm CursorX_x86_64 | grep main` 列出所有函数
- [ ] 代码签名状态 — `codesign -dvvv Mac/CursorX.app`（是否为自签名/无签名）

### 快速分析命令集

```bash
# 1. 确认架构
file Mac/CursorX.app/Contents/MacOS/CursorX
lipo -detailed_info Mac/CursorX.app/Contents/MacOS/CursorX

# 2. 枚举 Go 函数符号（分离 arm64 slice 后）
lipo -thin arm64 Mac/CursorX.app/Contents/MacOS/CursorX -output /tmp/CursorX_arm64
go tool nm /tmp/CursorX_arm64 2>/dev/null | grep -E "^[0-9a-f]+ T main\."

# 3. 提取所有可读字符串并过滤关键词
strings /tmp/CursorX_arm64 | grep -E \
  "cursor|ticket|auth|token|stripe|enterprise|api|http|sqlite|machine" \
  > /tmp/cursorx_strings.txt
wc -l /tmp/cursorx_strings.txt

# 4. 检查代码签名
codesign -dvvv Mac/CursorX.app 2>&1

# 5. 查看 Mach-O 节区结构
otool -l /tmp/CursorX_arm64 | grep -A4 "sectname"
```

---

## 相关文件清单

| 文件 | 绝对路径 | 重要性 |
|------|----------|--------|
| 主可执行文件 | `Mac/CursorX.app/Contents/MacOS/CursorX` | 最高 - 核心逻辑 |
| Bundle 配置 | `Mac/CursorX.app/Contents/Info.plist` | 中 - 元数据 |
| 应用图标 | `Mac/CursorX.app/Contents/Resources/iconfile.icns` | 低 - 无逻辑 |
