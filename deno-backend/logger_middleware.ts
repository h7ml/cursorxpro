// 日志中间件
// 用于记录所有 HTTP 请求的详细信息

interface LogEntry {
  timestamp: string;
  method: string;
  path: string;
  status: number;
  duration: number;
  ip: string;
  userAgent: string;
  requestBody?: unknown;
  responseBody?: unknown;
}

// ANSI 颜色代码
const colors = {
  reset: "\x1b[0m",
  bright: "\x1b[1m",
  dim: "\x1b[2m",
  
  // 前景色
  black: "\x1b[30m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  white: "\x1b[37m",
  
  // 背景色
  bgRed: "\x1b[41m",
  bgGreen: "\x1b[42m",
  bgYellow: "\x1b[43m",
  bgBlue: "\x1b[44m",
};

function getStatusColor(status: number): string {
  if (status >= 500) return colors.red;
  if (status >= 400) return colors.yellow;
  if (status >= 300) return colors.cyan;
  if (status >= 200) return colors.green;
  return colors.white;
}

function getMethodColor(method: string): string {
  switch (method) {
    case "GET": return colors.blue;
    case "POST": return colors.green;
    case "PUT": return colors.yellow;
    case "PATCH": return colors.magenta;
    case "DELETE": return colors.red;
    default: return colors.white;
  }
}

function formatDuration(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function getClientIp(req: Request): string {
  return req.headers.get("x-forwarded-for")?.split(",")[0].trim() 
    || req.headers.get("x-real-ip") 
    || "unknown";
}

export async function logRequest(
  req: Request,
  handler: (req: Request) => Promise<Response>
): Promise<Response> {
  const startTime = performance.now();
  const url = new URL(req.url);
  const method = req.method;
  const path = url.pathname + url.search;
  const ip = getClientIp(req);
  const userAgent = req.headers.get("user-agent") || "unknown";

  // 记录请求体（仅对 POST/PUT/PATCH）
  let requestBody: unknown = undefined;
  if (["POST", "PUT", "PATCH"].includes(method)) {
    try {
      const clonedReq = req.clone();
      const contentType = req.headers.get("content-type");
      if (contentType?.includes("application/json")) {
        requestBody = await clonedReq.json();
      }
    } catch {
      // 忽略解析错误
    }
  }

  // 执行请求处理
  const response = await handler(req);
  
  const endTime = performance.now();
  const duration = endTime - startTime;
  const status = response.status;

  // 记录响应体（仅对 JSON）
  let responseBody: unknown = undefined;
  const contentType = response.headers.get("content-type");
  if (contentType?.includes("application/json")) {
    try {
      const clonedRes = response.clone();
      responseBody = await clonedRes.json();
    } catch {
      // 忽略解析错误
    }
  }

  // 构造日志条目
  const logEntry: LogEntry = {
    timestamp: new Date().toISOString(),
    method,
    path,
    status,
    duration,
    ip,
    userAgent,
    requestBody,
    responseBody,
  };

  // 打印彩色日志
  const methodColor = getMethodColor(method);
  const statusColor = getStatusColor(status);
  const durationStr = formatDuration(duration);
  
  console.log(
    `${colors.dim}[${logEntry.timestamp}]${colors.reset} ` +
    `${methodColor}${colors.bright}${method.padEnd(7)}${colors.reset} ` +
    `${statusColor}${status}${colors.reset} ` +
    `${colors.cyan}${path}${colors.reset} ` +
    `${colors.dim}${durationStr}${colors.reset} ` +
    `${colors.dim}${ip}${colors.reset}`
  );

  // 如果是 API 请求，打印详细信息
  if (path.startsWith("/api/") || path.startsWith("/admin/api/")) {
    if (requestBody) {
      console.log(`  ${colors.dim}→ Request:${colors.reset}`, JSON.stringify(requestBody, null, 2));
    }
    if (responseBody) {
      console.log(`  ${colors.dim}← Response:${colors.reset}`, JSON.stringify(responseBody, null, 2));
    }
  }

  // 如果是错误响应，打印警告
  if (status >= 400) {
    console.log(`  ${colors.red}⚠ Error Response${colors.reset}`);
  }

  return response;
}

// 简化版日志（不记录请求/响应体）
export async function logRequestSimple(
  req: Request,
  handler: (req: Request) => Promise<Response>
): Promise<Response> {
  const startTime = performance.now();
  const url = new URL(req.url);
  const method = req.method;
  const path = url.pathname + url.search;
  const ip = getClientIp(req);

  const response = await handler(req);
  
  const endTime = performance.now();
  const duration = endTime - startTime;
  const status = response.status;

  const methodColor = getMethodColor(method);
  const statusColor = getStatusColor(status);
  const durationStr = formatDuration(duration);
  
  console.log(
    `${colors.dim}[${new Date().toISOString()}]${colors.reset} ` +
    `${methodColor}${colors.bright}${method.padEnd(7)}${colors.reset} ` +
    `${statusColor}${status}${colors.reset} ` +
    `${colors.cyan}${path}${colors.reset} ` +
    `${colors.dim}${durationStr}${colors.reset} ` +
    `${colors.dim}${ip}${colors.reset}`
  );

  return response;
}
