"""Validate a user's own Discord bot and build its least-privilege invite."""

from __future__ import annotations

import aiohttp

BOT_PERMISSIONS = 1166352


async def validate_bot_token(token: str) -> dict:
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Paste your Discord bot token first.")
    token = token.strip()
    if token.lower().startswith("bot "):
        token = token[4:].strip()
    async with aiohttp.ClientSession(
        headers={"Authorization": "Bot " + token},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as session:
        async def get(route: str):
            async with session.get("https://discord.com/api/v10" + route) as response:
                if response.status == 401:
                    raise ValueError("Discord rejected this bot token. Copy the token from your application's Bot page.")
                if response.status != 200:
                    raise ValueError(f"Discord returned HTTP {response.status}. Try again in a moment.")
                return await response.json()

        app = await get("/oauth2/applications/@me")
        user = await get("/users/@me")
        guilds = await get("/users/@me/guilds")
    if not user.get("bot"):
        raise ValueError("Use a bot token, not a personal Discord account token.")
    app_id = app["id"]
    return {
        "application_id": app_id,
        "bot_id": user["id"],
        "bot_name": user["username"],
        "invite_url": f"https://discord.com/oauth2/authorize?client_id={app_id}&scope=bot+applications.commands&permissions={BOT_PERMISSIONS}",
        "servers": [{"id": guild["id"], "name": guild["name"]} for guild in guilds],
    }
