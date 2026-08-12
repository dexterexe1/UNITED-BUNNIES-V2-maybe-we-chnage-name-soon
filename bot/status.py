"""
status.py — Keep-alive server and bot status publishing to the dashboard.
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import os
from threading import Thread
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import aiohttp

from bot.config import bot, BOT_STATUS_URL, BOT_API_SECRET


class KeepAliveHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")


def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = ThreadingHTTPServer(('0.0.0.0', port), KeepAliveHandler)
    print(f"📡 Internal web server listening on port {port}...")
    server.serve_forever()


async def publish_bot_status():
    """Sends bot health metrics + the real guild list to the website dashboard.

    Called once on_ready and then every 15s from status_loop() below. The
    guild list here is what powers the developer view's server picker on
    the dashboard (GET /api/bot/guilds) — no more hardcoded/demo servers.
    """
    if not BOT_STATUS_URL:
        return
    try:
        guilds_payload = [
            {
                "id": str(g.id),
                "name": g.name,
                "icon": str(g.icon.key) if g.icon else None,
                "memberCount": g.member_count or 0,
            }
            for g in bot.guilds
        ]
        payload = {
            "online": bot.is_ready(),
            "guildCount": len(bot.guilds),
            "memberCount": sum(g.member_count or 0 for g in bot.guilds),
            "ping": round(bot.latency * 1000) if bot.latency else 0,
            "guilds": guilds_payload,
        }
        headers = {"x-bot-secret": BOT_API_SECRET} if BOT_API_SECRET else {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(BOT_STATUS_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    print(f"⚠️ Status post failed: {resp.status} {await resp.text()}")
    except Exception as e:
        print(f"❌ Error publishing bot status: {e}")
