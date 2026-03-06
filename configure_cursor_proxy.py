#!/usr/bin/env python3
"""
configure_cursor_proxy.py - 将 Cursor 的 API 请求重定向到自定义代理

原理：
  Cursor 发出 AI 请求时，使用 state.vscdb 中的两个关键值：
    1. cursorAuth/accessToken  → Bearer Token（身份凭证）
    2. cursorai/serverConfig   → 服务端配置（含 agentUrlConfig.agentUrl）

  本脚本同时替换这两个值，实现无感知代理跳转：
    Cursor → 代理服务器（如 cursor2api-go.zeabur.app）→ 真实 AI

环境变量：
  CURSOR_PROXY_URL    代理服务器地址，如 https://cursor2api-go.zeabur.app
  CURSOR_PROXY_TOKEN  代理服务器的 Bearer Token（从代理服务商获取）

用法：
  export CURSOR_PROXY_URL=https://cursor2api-go.zeabur.app
  export CURSOR_PROXY_TOKEN=your_bearer_token_here
  python3 configure_cursor_proxy.py

  # 还原到官方服务器
  python3 configure_cursor_proxy.py --restore
"""

import os
import sys
import json
import sqlite3
import shutil
import platform
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────
# Cursor state.vscdb 路径
# ──────────────────────────────────────────────────────────
def get_db_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Cursor/User/globalStorage/state.vscdb"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Cursor/User/globalStorage/state.vscdb"
    elif system == "Linux":
        return Path.home() / ".config/Cursor/User/globalStorage/state.vscdb"
    else:
        raise RuntimeError(f"不支持的平台: {system}")


# ──────────────────────────────────────────────────────────
# Cursor 官方默认服务地址
# ──────────────────────────────────────────────────────────
OFFICIAL_AGENT_URL  = "https://agent.us.api5.cursor.sh"
OFFICIAL_AGENTN_URL = "https://agentn.us.api5.cursor.sh"
OFFICIAL_API2_URL   = "https://api2.cursor.sh"


# ──────────────────────────────────────────────────────────
# 读/写 state.vscdb
# ──────────────────────────────────────────────────────────
def read_kv(db_path: Path, key: str) -> str | None:
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute("SELECT value FROM ItemTable WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None


def write_kv(db_path: Path, key: str, value: str):
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()


def delete_kv(db_path: Path, key: str):
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DELETE FROM ItemTable WHERE key=?", (key,))
        conn.commit()


# ──────────────────────────────────────────────────────────
# 备份 / 还原
# ──────────────────────────────────────────────────────────
BACKUP_FILE = Path.home() / ".cursor_proxy_backup.json"


def save_backup(db_path: Path):
    """备份原始 token 和 serverConfig"""
    data = {
        "timestamp": datetime.now().isoformat(),
        "accessToken":  read_kv(db_path, "cursorAuth/accessToken"),
        "refreshToken": read_kv(db_path, "cursorAuth/refreshToken"),
        "serverConfig": read_kv(db_path, "cursorai/serverConfig"),
        "stripeMembershipType":    read_kv(db_path, "cursorAuth/stripeMembershipType"),
        "stripeSubscriptionStatus": read_kv(db_path, "cursorAuth/stripeSubscriptionStatus"),
    }
    BACKUP_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[备份] 原始配置已保存到 {BACKUP_FILE}")


def restore_backup(db_path: Path):
    """从备份还原"""
    if not BACKUP_FILE.exists():
        print("[错误] 未找到备份文件，无法还原")
        sys.exit(1)

    data = json.loads(BACKUP_FILE.read_text())
    print(f"[还原] 备份时间: {data.get('timestamp')}")

    if data.get("accessToken"):
        write_kv(db_path, "cursorAuth/accessToken", data["accessToken"])
    if data.get("refreshToken"):
        write_kv(db_path, "cursorAuth/refreshToken", data["refreshToken"])
    if data.get("serverConfig"):
        write_kv(db_path, "cursorai/serverConfig", data["serverConfig"])
    if data.get("stripeMembershipType"):
        write_kv(db_path, "cursorAuth/stripeMembershipType", data["stripeMembershipType"])
    if data.get("stripeSubscriptionStatus"):
        write_kv(db_path, "cursorAuth/stripeSubscriptionStatus", data["stripeSubscriptionStatus"])

    print("[还原] 已恢复到官方服务器配置，请重启 Cursor")


# ──────────────────────────────────────────────────────────
# 代理配置核心逻辑
# ──────────────────────────────────────────────────────────
def apply_proxy(db_path: Path, proxy_url: str, proxy_token: str):
    """
    将 Cursor 的请求路由到代理服务器：
      1. 替换 cursorAuth/accessToken  → 代理 Bearer Token
      2. 替换 cursorai/serverConfig   → agentUrl 改为代理地址
      3. 标记为 Pro 会员（避免 Cursor UI 提示升级）
    """
    # 清理 proxy_url 末尾斜杠
    proxy_url = proxy_url.rstrip("/")

    # ── 1. 替换 Bearer Token ──
    print(f"[配置] 写入代理 Token → cursorAuth/accessToken")
    write_kv(db_path, "cursorAuth/accessToken", proxy_token)
    write_kv(db_path, "cursorAuth/refreshToken", proxy_token)

    # ── 2. 替换 serverConfig 中的 agentUrl ──
    raw_config = read_kv(db_path, "cursorai/serverConfig")
    if raw_config:
        try:
            config = json.loads(raw_config)
        except json.JSONDecodeError:
            config = {}
    else:
        config = {}

    # 将 agentUrl/agentnUrl 指向代理
    config.setdefault("agentUrlConfig", {})
    config["agentUrlConfig"]["agentUrl"]  = proxy_url
    config["agentUrlConfig"]["agentnUrl"] = proxy_url

    print(f"[配置] 写入代理 agentUrl → {proxy_url}")
    write_kv(db_path, "cursorai/serverConfig", json.dumps(config, ensure_ascii=False))

    # ── 3. 标记 Pro 会员（使 Cursor UI 不弹升级提示）──
    write_kv(db_path, "cursorAuth/stripeMembershipType", "pro")
    write_kv(db_path, "cursorAuth/stripeSubscriptionStatus", "active")

    print(f"[配置] 已标记会员状态为 Pro/active")


# ──────────────────────────────────────────────────────────
# 打印当前状态
# ──────────────────────────────────────────────────────────
def show_status(db_path: Path):
    print("\n" + "=" * 60)
    print("当前 Cursor 代理状态")
    print("=" * 60)

    token = read_kv(db_path, "cursorAuth/accessToken") or ""
    config_raw = read_kv(db_path, "cursorai/serverConfig") or "{}"
    membership = read_kv(db_path, "cursorAuth/stripeMembershipType") or "unknown"
    status = read_kv(db_path, "cursorAuth/stripeSubscriptionStatus") or "unknown"

    try:
        config = json.loads(config_raw)
        agent_url = config.get("agentUrlConfig", {}).get("agentUrl", "N/A")
    except Exception:
        agent_url = "N/A"

    print(f"  accessToken : {token[:40]}..." if len(token) > 40 else f"  accessToken : {token}")
    print(f"  agentUrl    : {agent_url}")
    print(f"  membership  : {membership} / {status}")

    if agent_url == OFFICIAL_AGENT_URL:
        print("\n  [状态] 使用官方 Cursor 服务器")
    else:
        print(f"\n  [状态] 使用自定义代理: {agent_url}")
    print("=" * 60 + "\n")


# ──────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────
def main():
    restore_mode = "--restore" in sys.argv
    status_mode  = "--status" in sys.argv

    db_path = get_db_path()
    if not db_path.exists():
        print(f"[错误] 找不到 Cursor 数据库: {db_path}")
        print("  请确认 Cursor IDE 已安装并至少启动过一次")
        sys.exit(1)

    print("=" * 60)
    print("Cursor 代理配置工具")
    print("=" * 60)
    print(f"数据库路径: {db_path}\n")

    # ── 仅查看状态 ──
    if status_mode:
        show_status(db_path)
        return

    # ── 还原模式 ──
    if restore_mode:
        restore_backup(db_path)
        show_status(db_path)
        return

    # ── 代理配置模式 ──
    proxy_url   = os.environ.get("CURSOR_PROXY_URL", "").strip()
    proxy_token = os.environ.get("CURSOR_PROXY_TOKEN", "").strip()

    if not proxy_url:
        print("[错误] 请设置环境变量 CURSOR_PROXY_URL")
        print("  export CURSOR_PROXY_URL=https://cursor2api-go.zeabur.app")
        sys.exit(1)

    if not proxy_token:
        print("[错误] 请设置环境变量 CURSOR_PROXY_TOKEN")
        print("  export CURSOR_PROXY_TOKEN=your_bearer_token_here")
        sys.exit(1)

    # 先备份
    save_backup(db_path)

    # 应用代理配置
    apply_proxy(db_path, proxy_url, proxy_token)

    show_status(db_path)

    print("配置完成！请重启 Cursor IDE 以生效。")
    print()
    print("还原命令:")
    print("  python3 configure_cursor_proxy.py --restore")
    print()
    print("查看当前状态:")
    print("  python3 configure_cursor_proxy.py --status")


if __name__ == "__main__":
    main()
