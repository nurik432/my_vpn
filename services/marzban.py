import aiohttp
import ssl
from typing import Optional

# Отключаем SSL проверку для локального Marzban
_connector = aiohttp.TCPConnector(ssl=False)


class MarzbanAPI:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: Optional[str] = None

    async def get_token(self) -> str:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                f"{self.base_url}/api/admin/token",
                data={"username": self.username, "password": self.password},
            ) as resp:
                data = await resp.json()
                self.token = data["access_token"]
                return self.token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def create_user(self, username: str, data_limit_gb: int = 10, expire_days: int = 30) -> dict:
        await self.get_token()
        import time
        expire_ts = int(time.time()) + expire_days * 86400
        payload = {
            "username": username,
            "proxies": {"vless": {"flow": ""}},
            "inbounds": {"vless": ["VLESS_REALITY"]},
            "data_limit": data_limit_gb * 1024 ** 3,
            "expire": expire_ts,
        }
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                f"{self.base_url}/api/user",
                json=payload,
                headers=self._headers(),
            ) as resp:
                return await resp.json()

    async def get_user(self, username: str) -> dict:
        await self.get_token()
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(
                f"{self.base_url}/api/user/{username}",
                headers=self._headers(),
            ) as resp:
                return await resp.json()

    async def get_user_links(self, username: str) -> list[str]:
        user = await self.get_user(username)
        return user.get("links", [])

    async def reset_user_traffic(self, username: str) -> dict:
        await self.get_token()
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                f"{self.base_url}/api/user/{username}/reset",
                headers=self._headers(),
            ) as resp:
                return await resp.json()

    async def extend_user(self, username: str, expire_days: int = 30) -> dict:
        await self.get_token()
        import time
        user = await self.get_user(username)
        current_expire = user.get("expire") or int(time.time())
        new_expire = max(current_expire, int(time.time())) + expire_days * 86400
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.put(
                f"{self.base_url}/api/user/{username}",
                json={"expire": new_expire},
                headers=self._headers(),
            ) as resp:
                return await resp.json()

    async def get_user_traffic(self, username: str) -> dict:
        user = await self.get_user(username)
        used = user.get("used_traffic", 0)
        total = user.get("data_limit", 0)
        return {
            "used_gb": round(used / 1024 ** 3, 2),
            "total_gb": round(total / 1024 ** 3, 2),
            "remaining_gb": round((total - used) / 1024 ** 3, 2),
        }