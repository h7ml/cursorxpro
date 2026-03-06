# CursorX API 请求示例

## 激活请求

### 端点
```
POST https://cursorxpro.deno.dev/api/tickets/use
```

### 请求头
```http
Content-Type: application/json
```

### 请求体结构（加密前）
```json
{
  "ticketCode": "NQXS14YS",
  "machineCode": "a1b2c3d4e5f6...(64字符SHA256哈希)",
  "platform": "MAC"
}
```

### 实际发送的请求体（AES加密后）
```json
{
  "data": "<Base64编码的AES加密数据>"
}
```

### 加密算法
- **算法**: AES-256-CBC (CryptoJS)
- **密钥**: `nKEg32K9jsdJRMSA2pcn83LM9sUUwq29`
- **模式**: CBC
- **填充**: PKCS7
- **输出**: Base64

---

## 成功响应

### 响应体（加密）
```json
{
  "code": 200,
  "message": "success",
  "data": "<Base64编码的AES加密数据>"
}
```

### 解密后的 data 字段
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "id": "usr_abc123def456"
}
```

---

## 失败响应

### 票据无效
```json
{
  "code": 400,
  "message": "车票无效或已使用",
  "data": null
}
```

### 票据已过期
```json
{
  "code": 403,
  "message": "车票已过期",
  "data": null
}
```

### 机器码不匹配
```json
{
  "code": 409,
  "message": "该车票已绑定其他设备",
  "data": null
}
```

---

## 本地数据库更新

成功获取 token 后，CursorX 会调用 Go 后端更新 Cursor 的 SQLite 数据库：

```javascript
// Wails 桥接调用
window.go.main.App.UpdateCursorAuth(id, token)
```

### 更新的字段
```sql
-- 表: ItemTable (在 state.vscdb 中)
UPDATE ItemTable SET value = ? WHERE key = 'cursorAuth/accessToken';
UPDATE ItemTable SET value = ? WHERE key = 'cursorAuth/refreshToken';
UPDATE ItemTable SET value = 'enterprise' WHERE key = 'cursorAuth/stripeMembershipType';
UPDATE ItemTable SET value = 'CursorX:usr_abc123def456' WHERE key = 'cursorAuth/cachedEmail';
```

---

## 机器指纹生成算法

```javascript
async function generateMachineCode() {
  const fingerprint = `${window.screen.width}x${window.screen.height}x${window.screen.colorDepth}` +
                      `|${new Date().getTimezoneOffset()}` +
                      `|${navigator.language}` +
                      `|${navigator.platform}` +
                      `|${navigator.hardwareConcurrency || ''}` +
                      `|${navigator.deviceMemory || ''}`;

  const encoder = new TextEncoder();
  const data = encoder.encode(fingerprint);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}
```

### 示例输出
```
输入: "1920x1080x24|-480|zh-CN|MacIntel|8|16"
输出: "7f3a8b2c1d9e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"
```

---

## 前端界面元素

### 输入框
```html
<input
  id="ticketInput"
  type="text"
  placeholder="请输入车票"
  value="NQXS14YS"
/>
```

### 提交按钮
```html
<button
  className="submit-btn"
  onClick={handleSubmit}
  disabled={loading || !ticketCode.trim()}
>
  {loading ? "上车中..." : "立即上车"}
</button>
```

### 成功提示
```
恭喜！上车成功~
请重启Cursor以生效
```

---

## 调试方法

### 1. 拦截请求（使用 Chrome DevTools）
打开 CursorX 应用后，在 WebView 中按 `Cmd+Option+I` (Mac) 或 `F12` (Win) 打开开发者工具，切换到 Network 标签页。

### 2. 查看加密前的数据
在 Console 中执行：
```javascript
// 拦截 fetch 请求
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  console.log('Request:', args);
  const response = await originalFetch(...args);
  const clone = response.clone();
  const data = await clone.json();
  console.log('Response:', data);
  return response;
};
```

### 3. 手动解密响应
```javascript
// 需要先加载 CryptoJS（已内置在应用中）
function decryptResponse(encryptedData) {
  const key = CryptoJS.enc.Utf8.parse('nKEg32K9jsdJRMSA2pcn83LM9sUUwq29');
  const decrypted = CryptoJS.AES.decrypt(encryptedData, key, {
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7
  });
  return JSON.parse(decrypted.toString(CryptoJS.enc.Utf8));
}
```
