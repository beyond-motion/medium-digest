#!/usr/bin/env python3
"""notify_telegram.py — Medium 导读站每日管线的 Telegram 结果通知（零依赖）

用法：
  python3 scripts/notify_telegram.py --status success  --message "新增 3 篇导读"
  python3 scripts/notify_telegram.py --status no_update --message "今日无新导读"
  python3 scripts/notify_telegram.py --status failure --stage build --error "..." 

凭据从仓库根目录 .env.local 读取（TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID），缺失时打印
[telegram skipped] 并正常退出（通知失败不阻塞主流程）。
"""
import argparse
import pathlib
import sys
import urllib.parse
import urllib.request

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

    text = "\n".join(lines)
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        with urllib.request.urlopen(api, data=data, timeout=15) as resp:
            ok = json_ok(resp.read())
            print(f"[telegram {'sent' if ok else 'unexpected response'}]")
            return 0
    except Exception as e:
        print(f"[telegram failed] {e}")
        return 1


def json_ok(raw: bytes) -> bool:
    import json
    try:
        return bool(json.loads(raw).get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
