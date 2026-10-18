#!/usr/bin/env python3
"""notify_telegram.py — Medium 导读站每日管线的 Telegram 结果通知（零依赖）

用法：
  python3 scripts/notify_telegram.py --status success  --message "新增 3 篇导读"
  python3 scripts/notify_telegram.py --status no_update --message "今日无新导读"
  python3 scripts/notify_telegram.py --status failure --stage build --error "..." 

凭据从仓库根目录 .env.local 读取（TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID），缺失时打印
[telegram skipped] 并正常退出（通知失败不阻塞主流程）。

退出码：0 = 已发送或跳过；2 = 发送失败（含 3 次尝试仍失败；区别于主流程失败的 1，
调用方按需感知，不误标整日失败）。
"""
import argparse
import http.client
import pathlib
import sys
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICON = {"success": "✅", "no_update": "📭", "failure": "❌"}


def load_env() -> dict:
    env = {}
    p = ROOT / ".env.local"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def send(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """单次发送；返回 (ok, 诊断)。ok 仅当 Telegram 回 {"ok": true}，否则附 HTTP 状态。"""
    # token 只 quote 进路径；host 是字面常量，结构上杜绝 SSRF（env 值无法改写目标主机）
    path = "/bot" + urllib.parse.quote(token, safe="") + "/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    conn = http.client.HTTPSConnection("api.telegram.org", timeout=15)
    try:
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        if json_ok(raw):
            return True, f"http={resp.status}"
        return False, f"http={resp.status} body={raw[:120].decode('utf-8', 'ignore')}"
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", choices=["success", "no_update", "failure"], required=True)
    ap.add_argument("--message", default="")
    ap.add_argument("--stage", default="")
    ap.add_argument("--error", default="")
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--url", default="")
    args = ap.parse_args()

    env = load_env()
    token, chat_id = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[telegram skipped] 缺少 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
        return 0

    lines = [f"{ICON.get(args.status, '•')} Medium 导读站 · {args.status}"]
    if args.message:
        lines.append(args.message)
    if args.count:
        lines.append(f"新增导读：{args.count} 篇")
    if args.status == "failure":
        lines.append(f"阶段：{args.stage or 'unknown'}")
        if args.error:
            lines.append(f"错误：{args.error[:300]}")
    site = env.get("SITE_URL", "https://beyond-motion.github.io/medium-digest/")
    if args.url:
        lines.append(args.url)
    else:
        lines.append(site)

    text = "\n".join(lines)[:4000]  # Telegram 上限 4096 字符，留余量防静默拒绝
    ok, detail = False, ""
    for attempt in range(3):  # 首发 + 两次退避重试（2s/5s）
        if attempt:
            time.sleep(2 if attempt == 1 else 5)
        try:
            ok, detail = send(token, chat_id, text)
        except Exception as e:
            ok, detail = False, str(e)
        if ok:
            break
    if ok:
        print("[telegram sent]")
        return 0
    print(f"[telegram FAILED] {detail}（3 次尝试均失败）")
    return 2


def json_ok(raw: bytes) -> bool:
    import json
    try:
        return bool(json.loads(raw).get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
