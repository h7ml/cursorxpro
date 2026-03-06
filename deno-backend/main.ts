/// <reference lib="deno.ns" />

import { logRequest } from "./logger_middleware.ts";

type PlatformType = "MAC" | "WINDOWS" | "LINUX" | "OTHER";

type TicketStatus = "active" | "disabled" | "used";

interface TicketRecord {
  code: string;
  status: TicketStatus;
  createdAt: string;
  updatedAt: string;
  expiresAt: string | null;
  boundMachineCode: string | null;
  lastUsedAt: string | null;
  note: string;
}

interface UsageLog {
  id: string;
  ticketCode: string;
  machineCode: string;
  platform: string;
  success: boolean;
  message: string;
  ip: string;
  userAgent: string;
  createdAt: string;
}

interface AdminUser {
  username: string;
  passwordHash: string;
  passwordSalt: string;
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
}

interface AdminSession {
  tokenHash: string;
  username: string;
  createdAt: string;
  expiresAt: string;
}

interface ActivationRequestBody {
  ticketCode: string;
  machineCode: string;
  platform: PlatformType | string;
}

const config = {
  host: Deno.env.get("HOST") ?? "0.0.0.0",
  port: Number(Deno.env.get("PORT") ?? "8000"),
  apiHost: Deno.env.get("PUBLIC_API_HOST") ?? "https://cursorxpro.deno.dev",
  upstreamApiBaseUrl: (Deno.env.get("UPSTREAM_API_BASE_URL") ?? "").trim(),
  upstreamBearerToken: (Deno.env.get("UPSTREAM_AUTH_BEARER_TOKEN") ?? "").trim(),
  upstreamTimeoutMs: Number(Deno.env.get("UPSTREAM_TIMEOUT_MS") ?? "15000"),
  aesKey: Deno.env.get("AES_KEY") ?? "nKEg32K9jsdJRMSA2pcn83LM9sUUwq29",
  jwtSecret: Deno.env.get("JWT_SECRET") ?? "replace_this_with_random_secret",
  sessionTtlHours: Number(Deno.env.get("SESSION_TTL_HOURS") ?? "72"),
  adminBootstrapUsername: Deno.env.get("ADMIN_BOOTSTRAP_USERNAME") ?? "admin",
  adminBootstrapPassword: Deno.env.get("ADMIN_BOOTSTRAP_PASSWORD") ?? "ChangeMe_123456",
  navigationLinks: [
    { text: "官方文档", url: "https://docs.cursor.com", icon: "book" },
    { text: "状态页", url: "https://status.cursor.com", icon: "pulse" }
  ],
};

if (config.aesKey.length !== 32) {
  throw new Error("AES_KEY 必须是 32 字符（AES-256）");
}

if (typeof Deno.openKv !== "function") {
  throw new Error("当前 Deno 未启用 KV，请使用 --unstable-kv 启动。");
}

const kv = await Deno.openKv();
const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

function nowIso(): string {
  return new Date().toISOString();
}

function toBase64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

function fromBase64(value: string): ArrayBuffer {
  const bin = atob(value);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out.buffer.slice(out.byteOffset, out.byteOffset + out.byteLength);
}

function toBase64Url(bytes: Uint8Array): string {
  return toBase64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function toBase64UrlFromString(value: string): string {
  return toBase64Url(textEncoder.encode(value));
}

function randomHex(length: number): string {
  const bytes = crypto.getRandomValues(new Uint8Array(Math.ceil(length / 2)));
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, length);
}

function randomCode(length = 8): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(bytes)
    .map((b) => chars[b % chars.length])
    .join("");
}

async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", textEncoder.encode(input));
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function derivePasswordHash(password: string, saltHex: string): Promise<string> {
  const salt = Uint8Array.from(saltHex.match(/.{1,2}/g)!.map((x) => Number.parseInt(x, 16)));
  const key = await crypto.subtle.importKey("raw", textEncoder.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations: 120_000 },
    key,
    256,
  );
  return Array.from(new Uint8Array(bits))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function encryptAesJson(payload: unknown): Promise<string> {
  const keyBytes = textEncoder.encode(config.aesKey);
  const iv = keyBytes.slice(0, 16);
  const cryptoKey = await crypto.subtle.importKey("raw", keyBytes, "AES-CBC", false, ["encrypt"]);
  const plain = textEncoder.encode(JSON.stringify(payload));
  const encrypted = await crypto.subtle.encrypt({ name: "AES-CBC", iv }, cryptoKey, plain);
  return toBase64(new Uint8Array(encrypted));
}

async function decryptAesJson<T>(encryptedBase64: string): Promise<T> {
  const keyBytes = textEncoder.encode(config.aesKey);
  const iv = keyBytes.slice(0, 16);
  const cryptoKey = await crypto.subtle.importKey("raw", keyBytes, "AES-CBC", false, ["decrypt"]);
  const encrypted = fromBase64(encryptedBase64);
  const decrypted = await crypto.subtle.decrypt({ name: "AES-CBC", iv }, cryptoKey, encrypted);
  return JSON.parse(textDecoder.decode(decrypted)) as T;
}

async function createPseudoJwt(userId: string, machineCode: string): Promise<string> {
  const header = toBase64UrlFromString(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = toBase64UrlFromString(
    JSON.stringify({
      sub: userId,
      machineCode,
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 30,
    }),
  );
  const signingInput = `${header}.${payload}`;
  const key = await crypto.subtle.importKey(
    "raw",
    textEncoder.encode(config.jwtSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, textEncoder.encode(signingInput));
  return `${signingInput}.${toBase64Url(new Uint8Array(signature))}`;
}

function corsHeaders(origin = "*"): Headers {
  const headers = new Headers();
  headers.set("Access-Control-Allow-Origin", origin);
  headers.set("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS");
  headers.set("Access-Control-Allow-Headers", "Content-Type,Authorization");
  headers.set("Access-Control-Allow-Credentials", "true");
  return headers;
}

function json(data: unknown, status = 200, extraHeaders?: HeadersInit): Response {
  const headers = new Headers(extraHeaders);
  headers.set("Content-Type", "application/json; charset=utf-8");
  const cors = corsHeaders();
  cors.forEach((v, k) => headers.set(k, v));
  return new Response(JSON.stringify(data), { status, headers });
}

function html(content: string, status = 200, extraHeaders?: HeadersInit): Response {
  const headers = new Headers(extraHeaders);
  headers.set("Content-Type", "text/html; charset=utf-8");
  const cors = corsHeaders();
  cors.forEach((v, k) => headers.set(k, v));
  return new Response(content, { status, headers });
}

async function readJson<T>(req: Request): Promise<T> {
  return (await req.json()) as T;
}

function getClientIp(req: Request): string {
  return req.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "unknown";
}

function getCookie(req: Request, key: string): string | null {
  const cookie = req.headers.get("cookie");
  if (!cookie) return null;
  for (const pair of cookie.split(";")) {
    const [k, ...rest] = pair.trim().split("=");
    if (k === key) return decodeURIComponent(rest.join("="));
  }
  return null;
}

async function upsertUsageLog(item: UsageLog): Promise<void> {
  await kv.set(["usageLogs", item.createdAt, item.id], item);
}

async function getTicket(code: string): Promise<TicketRecord | null> {
  const result = await kv.get<TicketRecord>(["tickets", code]);
  return result.value;
}

async function saveTicket(ticket: TicketRecord): Promise<void> {
  await kv.set(["tickets", ticket.code], ticket);
}

async function ensureBootstrapAdmin(): Promise<void> {
  const existing = await kv.get<AdminUser>(["admins", config.adminBootstrapUsername]);
  if (existing.value) return;
  const salt = randomHex(16);
  const passwordHash = await derivePasswordHash(config.adminBootstrapPassword, salt);
  const now = nowIso();
  const admin: AdminUser = {
    username: config.adminBootstrapUsername,
    passwordHash,
    passwordSalt: salt,
    createdAt: now,
    updatedAt: now,
    lastLoginAt: null,
  };
  await kv.set(["admins", admin.username], admin);
  console.log(`[bootstrap] 已创建管理员账号: ${admin.username}`);
}

async function createSession(username: string): Promise<string> {
  const raw = toBase64Url(crypto.getRandomValues(new Uint8Array(32)));
  const tokenHash = await sha256Hex(raw);
  const now = new Date();
  const expires = new Date(now.getTime() + config.sessionTtlHours * 3600 * 1000);
  const session: AdminSession = {
    tokenHash,
    username,
    createdAt: now.toISOString(),
    expiresAt: expires.toISOString(),
  };
  await kv.set(["adminSessions", tokenHash], session, { expireIn: config.sessionTtlHours * 3600 * 1000 });
  return raw;
}

async function deleteSession(token: string): Promise<void> {
  const tokenHash = await sha256Hex(token);
  await kv.delete(["adminSessions", tokenHash]);
}

async function resolveSession(req: Request): Promise<AdminSession | null> {
  const auth = req.headers.get("authorization");
  let token: string | null = null;
  if (auth?.startsWith("Bearer ")) token = auth.slice(7).trim();
  if (!token) token = getCookie(req, "admin_session");
  if (!token) return null;

  const tokenHash = await sha256Hex(token);
  const sessionRes = await kv.get<AdminSession>(["adminSessions", tokenHash]);
  const session = sessionRes.value;
  if (!session) return null;
  if (new Date(session.expiresAt).getTime() < Date.now()) {
    await kv.delete(["adminSessions", tokenHash]);
    return null;
  }
  return session;
}

function adminCookie(token: string): string {
  const maxAge = config.sessionTtlHours * 3600;
  return `admin_session=${encodeURIComponent(token)}; HttpOnly; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
}

function clearAdminCookie(): string {
  return "admin_session=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax";
}

async function handleUseTicket(req: Request): Promise<Response> {
  if (config.upstreamApiBaseUrl) {
    if (!config.upstreamBearerToken) {
      return json({ code: 500, message: "未配置 UPSTREAM_AUTH_BEARER_TOKEN", data: null }, 500);
    }

    try {
      const body = await req.text();
      const upstream = new URL("/api/tickets/use", config.upstreamApiBaseUrl).toString();
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), config.upstreamTimeoutMs);
      const resp = await fetch(upstream, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${config.upstreamBearerToken}`,
        },
        body,
        signal: controller.signal,
      });
      clearTimeout(timer);

      const text = await resp.text();
      const headers = new Headers();
      headers.set("Content-Type", resp.headers.get("content-type") ?? "application/json; charset=utf-8");
      const cors = corsHeaders();
      cors.forEach((v, k) => headers.set(k, v));
      return new Response(text, { status: resp.status, headers });
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown error";
      return json({ code: 502, message: `上游请求失败: ${message}`, data: null }, 502);
    }
  }

  try {
    const body = await readJson<{ data?: string }>(req);
    if (!body.data) {
      return json({ code: 400, message: "缺少 data 字段", data: null }, 400);
    }

    const payload = await decryptAesJson<ActivationRequestBody>(body.data);
    const { ticketCode, machineCode, platform } = payload;

    if (!ticketCode || !machineCode) {
      return json({ code: 400, message: "参数不完整", data: null }, 400);
    }

    const ticket = await getTicket(ticketCode);
    if (!ticket) {
      await upsertUsageLog({
        id: randomHex(12),
        ticketCode,
        machineCode,
        platform: String(platform ?? "OTHER"),
        success: false,
        message: "车票无效或不存在",
        ip: getClientIp(req),
        userAgent: req.headers.get("user-agent") ?? "",
        createdAt: nowIso(),
      });
      return json({ code: 400, message: "车票无效或已使用", data: null }, 200);
    }

    if (ticket.status === "disabled") {
      return json({ code: 403, message: "车票已禁用", data: null }, 200);
    }

    if (ticket.expiresAt && new Date(ticket.expiresAt).getTime() < Date.now()) {
      return json({ code: 403, message: "车票已过期", data: null }, 200);
    }

    if (ticket.boundMachineCode && ticket.boundMachineCode !== machineCode) {
      return json({ code: 409, message: "该车票已绑定其他设备", data: null }, 200);
    }

    const id = `usr_${randomHex(12)}`;
    const token = await createPseudoJwt(id, machineCode);

    const now = nowIso();
    ticket.boundMachineCode = machineCode;
    ticket.lastUsedAt = now;
    ticket.status = "used";
    ticket.updatedAt = now;
    await saveTicket(ticket);

    await upsertUsageLog({
      id: randomHex(12),
      ticketCode,
      machineCode,
      platform: String(platform ?? "OTHER"),
      success: true,
      message: "success",
      ip: getClientIp(req),
      userAgent: req.headers.get("user-agent") ?? "",
      createdAt: now,
    });

    const encryptedData = await encryptAesJson({ token, id });
    return json({ code: 200, message: "success", data: encryptedData }, 200);
  } catch (error) {
    const message = error instanceof Error ? error.message : "unknown error";
    return json({ code: 500, message: `服务异常: ${message}`, data: null }, 500);
  }
}

async function handleNavigationLinks(): Promise<Response> {
  if (config.upstreamApiBaseUrl) {
    if (!config.upstreamBearerToken) {
      return json({ code: 500, message: "未配置 UPSTREAM_AUTH_BEARER_TOKEN", data: null }, 500);
    }

    try {
      const upstream = new URL("/api/navigation/links", config.upstreamApiBaseUrl).toString();
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), config.upstreamTimeoutMs);
      const resp = await fetch(upstream, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${config.upstreamBearerToken}`,
        },
        signal: controller.signal,
      });
      clearTimeout(timer);

      const text = await resp.text();
      const headers = new Headers();
      headers.set("Content-Type", resp.headers.get("content-type") ?? "application/json; charset=utf-8");
      const cors = corsHeaders();
      cors.forEach((v, k) => headers.set(k, v));
      return new Response(text, { status: resp.status, headers });
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown error";
      return json({ code: 502, message: `上游请求失败: ${message}`, data: null }, 502);
    }
  }

  return json({ code: 200, message: "success", data: config.navigationLinks }, 200);
}

async function requireAdmin(req: Request): Promise<{ session: AdminSession } | Response> {
  const session = await resolveSession(req);
  if (!session) return json({ code: 401, message: "未登录或会话已过期" }, 401);
  return { session };
}

async function handleAdminLogin(req: Request): Promise<Response> {
  const body = await readJson<{ username?: string; password?: string }>(req);
  const username = body.username?.trim();
  const password = body.password ?? "";
  if (!username || !password) {
    return json({ code: 400, message: "用户名和密码必填" }, 400);
  }

  const adminRes = await kv.get<AdminUser>(["admins", username]);
  const admin = adminRes.value;
  if (!admin) return json({ code: 401, message: "用户名或密码错误" }, 401);

  const hash = await derivePasswordHash(password, admin.passwordSalt);
  if (hash !== admin.passwordHash) return json({ code: 401, message: "用户名或密码错误" }, 401);

  admin.lastLoginAt = nowIso();
  admin.updatedAt = nowIso();
  await kv.set(["admins", admin.username], admin);

  const token = await createSession(admin.username);
  return json(
    {
      code: 200,
      message: "success",
      data: {
        username: admin.username,
        token,
      },
    },
    200,
    { "Set-Cookie": adminCookie(token) },
  );
}

async function handleAdminLogout(req: Request): Promise<Response> {
  const auth = req.headers.get("authorization");
  const bearer = auth?.startsWith("Bearer ") ? auth.slice(7).trim() : null;
  const cookieToken = getCookie(req, "admin_session");
  const token = bearer || cookieToken;
  if (token) await deleteSession(token);
  return json({ code: 200, message: "success" }, 200, { "Set-Cookie": clearAdminCookie() });
}

async function handleAdminMe(req: Request): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;
  return json({ code: 200, data: { username: guarded.session.username } });
}

async function handleAdminTicketsList(req: Request): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;

  const url = new URL(req.url);
  const keyword = (url.searchParams.get("keyword") ?? "").trim().toUpperCase();
  const status = (url.searchParams.get("status") ?? "").trim();

  const list: TicketRecord[] = [];
  for await (const item of kv.list<TicketRecord>({ prefix: ["tickets"] })) {
    list.push(item.value);
  }

  const filtered = list
    .filter((t) => (keyword ? t.code.includes(keyword) : true))
    .filter((t) => (status ? t.status === status : true))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return json({ code: 200, data: filtered });
}

async function handleAdminTicketsCreate(req: Request): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;

  const body = await readJson<{ code?: string; expiresAt?: string | null; note?: string }>(req);
  const code = (body.code ?? "").trim().toUpperCase();
  if (!code) return json({ code: 400, message: "code 必填" }, 400);

  const existing = await getTicket(code);
  if (existing) return json({ code: 409, message: "车票已存在" }, 409);

  const now = nowIso();
  const ticket: TicketRecord = {
    code,
    status: "active",
    createdAt: now,
    updatedAt: now,
    expiresAt: body.expiresAt ?? null,
    boundMachineCode: null,
    lastUsedAt: null,
    note: body.note ?? "",
  };

  await saveTicket(ticket);
  return json({ code: 200, message: "success", data: ticket });
}

async function handleAdminTicketsBulkCreate(req: Request): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;

  const body = await readJson<{ count?: number; prefix?: string; expiresInDays?: number; note?: string }>(req);
  const count = Number(body.count ?? 1);
  if (!Number.isInteger(count) || count <= 0 || count > 500) {
    return json({ code: 400, message: "count 需在 1~500" }, 400);
  }

  const prefix = (body.prefix ?? "").trim().toUpperCase();
  const expiresInDays = body.expiresInDays;
  const expiresAt =
    typeof expiresInDays === "number" && expiresInDays > 0
      ? new Date(Date.now() + expiresInDays * 24 * 3600 * 1000).toISOString()
      : null;

  const created: TicketRecord[] = [];
  for (let i = 0; i < count; i++) {
    let code = `${prefix}${randomCode(8)}`;
    while (await getTicket(code)) {
      code = `${prefix}${randomCode(8)}`;
    }

    const now = nowIso();
    const ticket: TicketRecord = {
      code,
      status: "active",
      createdAt: now,
      updatedAt: now,
      expiresAt,
      boundMachineCode: null,
      lastUsedAt: null,
      note: body.note ?? "",
    };
    await saveTicket(ticket);
    created.push(ticket);
  }

  return json({ code: 200, data: created });
}

async function handleAdminTicketPatch(req: Request, ticketCode: string): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;

  const ticket = await getTicket(ticketCode);
  if (!ticket) return json({ code: 404, message: "车票不存在" }, 404);

  const body = await readJson<{
    status?: TicketStatus;
    expiresAt?: string | null;
    note?: string;
    unbindMachine?: boolean;
  }>(req);

  if (body.status) ticket.status = body.status;
  if (body.expiresAt !== undefined) ticket.expiresAt = body.expiresAt;
  if (body.note !== undefined) ticket.note = body.note;
  if (body.unbindMachine) ticket.boundMachineCode = null;
  ticket.updatedAt = nowIso();

  await saveTicket(ticket);
  return json({ code: 200, data: ticket });
}

async function handleAdminTicketDelete(req: Request, ticketCode: string): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;

  await kv.delete(["tickets", ticketCode]);
  return json({ code: 200, message: "success" });
}

async function handleAdminUsageLogs(req: Request): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;

  const url = new URL(req.url);
  const ticketCode = (url.searchParams.get("ticketCode") ?? "").trim().toUpperCase();
  const machineCode = (url.searchParams.get("machineCode") ?? "").trim();
  const limit = Math.min(Number(url.searchParams.get("limit") ?? "200"), 1000);

  const logs: UsageLog[] = [];
  for await (const item of kv.list<UsageLog>({ prefix: ["usageLogs"] })) {
    logs.push(item.value);
  }

  const filtered = logs
    .filter((l) => (ticketCode ? l.ticketCode === ticketCode : true))
    .filter((l) => (machineCode ? l.machineCode.includes(machineCode) : true))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .slice(0, limit);

  return json({ code: 200, data: filtered });
}

async function handleAdminStats(req: Request): Promise<Response> {
  const guarded = await requireAdmin(req);
  if (guarded instanceof Response) return guarded;

  let total = 0;
  let active = 0;
  let used = 0;
  let disabled = 0;
  for await (const item of kv.list<TicketRecord>({ prefix: ["tickets"] })) {
    total += 1;
    if (item.value.status === "active") active += 1;
    if (item.value.status === "used") used += 1;
    if (item.value.status === "disabled") disabled += 1;
  }

  let usageCount = 0;
  for await (const _item of kv.list<UsageLog>({ prefix: ["usageLogs"] })) {
    usageCount += 1;
  }

  return json({
    code: 200,
    data: {
      totalTickets: total,
      activeTickets: active,
      usedTickets: used,
      disabledTickets: disabled,
      usageCount,
    },
  });
}

const adminTemplate = await Deno.readTextFile(new URL("./admin.html", import.meta.url));
const indexTemplate = await Deno.readTextFile(new URL("./index.html", import.meta.url));

function indexPageHtml(): string {
  return indexTemplate.replaceAll("__API_HOST__", config.apiHost);
}


function adminPageHtml(): string {
  return adminTemplate.replaceAll("__API_HOST__", config.apiHost);
}

async function handleAdminApi(req: Request, url: URL): Promise<Response> {
  const path = url.pathname;

  if (path === "/admin/api/login" && req.method === "POST") return handleAdminLogin(req);
  if (path === "/admin/api/logout" && req.method === "POST") return handleAdminLogout(req);
  if (path === "/admin/api/me" && req.method === "GET") return handleAdminMe(req);

  if (path === "/admin/api/tickets" && req.method === "GET") return handleAdminTicketsList(req);
  if (path === "/admin/api/tickets" && req.method === "POST") return handleAdminTicketsCreate(req);
  if (path === "/admin/api/tickets/bulk" && req.method === "POST") return handleAdminTicketsBulkCreate(req);

  const ticketMatch = path.match(/^\/admin\/api\/tickets\/([A-Za-z0-9_-]+)$/);
  if (ticketMatch && req.method === "PATCH") return handleAdminTicketPatch(req, ticketMatch[1].toUpperCase());
  if (ticketMatch && req.method === "DELETE") return handleAdminTicketDelete(req, ticketMatch[1].toUpperCase());

  if (path === "/admin/api/usage-logs" && req.method === "GET") return handleAdminUsageLogs(req);
  if (path === "/admin/api/stats" && req.method === "GET") return handleAdminStats(req);

  return json({ code: 404, message: "Not Found" }, 404);
}

async function handleRequest(req: Request): Promise<Response> {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders() });
  }

  const url = new URL(req.url);

  if (url.pathname === "/healthz") {
    return json({ ok: true, now: nowIso() }, 200);
  }

  if (url.pathname === "/api/tickets/use" && req.method === "POST") {
    return handleUseTicket(req);
  }

  if (url.pathname === "/api/navigation/links" && req.method === "GET") {
    return handleNavigationLinks();
  }

  if (url.pathname === "/admin" || url.pathname === "/admin/") {
    return html(adminPageHtml());
  }

  if (url.pathname === "/" || url.pathname === "/index.html") {
    return html(indexPageHtml());
  }


  if (url.pathname.startsWith("/admin/api/")) {
    return handleAdminApi(req, url);
  }

  return json({ code: 404, message: "Not Found" }, 404);
}

await ensureBootstrapAdmin();

console.log(`CursorX Pro backend listening on http://${config.host}:${config.port}`);
console.log(`Admin panel: http://${config.host}:${config.port}/admin`);

Deno.serve({ hostname: config.host, port: config.port }, (req) => logRequest(req, handleRequest));
