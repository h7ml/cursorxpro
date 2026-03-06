# CursorX Pro Deno 后端

本后端与当前 CursorX 客户端协议保持兼容：
- `POST /api/tickets/use`
- 请求体 `{"data":"<AES-256-CBC Base64>"}`
- 密钥与加密行为兼容 CryptoJS（IV=密钥前16字节，PKCS7）

同时提供：
- 管理员认证（会话 + Bearer）
- 票据管理（单个创建、批量创建、状态修改、解绑、删除）
- 使用记录查询
- 管理后台页面（`/admin`）

## 1. 本地启动

```bash
cd deno-backend
cp .env.example .env
# 根据需要编辑环境变量

deno task dev
# 等价于：
# deno run --unstable-kv --allow-net --allow-env --allow-read --allow-write main.ts
```

默认地址：
- API: `http://127.0.0.1:8000`
- 管理后台: `http://127.0.0.1:8000/admin`

默认管理员：
- 用户名：`admin`
- 密码：`ChangeMe_123456`

首次启动后会自动写入 Deno KV，请立刻修改默认密码（当前代码为 bootstrap 账号，建议你后续补一个改密 API）。

## 2. 客户端 URL

你需要把客户端请求域名改为：
- `https://cursorxpro.deno.dev`

本仓库中可编辑文本里已替换完成。

## 3. 关键接口

### 激活接口
- `POST /api/tickets/use`
- 入参（解密后）：
  - `ticketCode`
  - `machineCode`
  - `platform`
- 出参（`code=200` 时 `data` 为 AES 加密）

### 导航接口
- `GET /api/navigation/links`

### 管理员认证
- `POST /admin/api/login`
- `POST /admin/api/logout`
- `GET /admin/api/me`

### 票据管理
- `GET /admin/api/tickets`
- `POST /admin/api/tickets`
- `POST /admin/api/tickets/bulk`
- `PATCH /admin/api/tickets/:code`
- `DELETE /admin/api/tickets/:code`

### 使用记录与统计
- `GET /admin/api/usage-logs`
- `GET /admin/api/stats`

## 4. Deno Deploy

建议配置：
- 入口文件：`deno-backend/main.ts`
- 环境变量：参考 `.env.example`
- 域名绑定：`cursorxpro.deno.dev`

> 注意：Deno Deploy 的 KV 与本地 KV 是不同实例，部署后请在 Deploy 环境中重新初始化管理员与票据数据。
