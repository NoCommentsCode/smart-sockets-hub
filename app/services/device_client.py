"""HTTP-клиент к прошивке ESP32. Повторяет контракт openapi.yaml."""
import httpx

from app.core.config import settings


class DeviceError(Exception):
    pass


class DeviceClient:
    def __init__(self, ip: str):
        self.base_url = f"http://{ip}:{settings.device_http_port}"

    async def _request(self, method: str, path: str) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=3.0, headers={"X-API-Key": settings.device_api_key}
            ) as client:
                resp = await client.request(method, self.base_url + path)
        except httpx.HTTPError as e:
            raise DeviceError(str(e)) from e
        if resp.status_code != 200:
            raise DeviceError(f"HTTP {resp.status_code}")
        try:
            return resp.json()
        except ValueError as e:
            raise DeviceError("Некорректный JSON от устройства") from e

    async def get_info(self) -> dict:
        return await self._request("GET", "/api/device/info")

    async def get_relays(self) -> dict:
        return await self._request("GET", "/api/relays/status")

    async def set_relay(self, relay_id: int, state: bool) -> dict:
        return await self._request("POST", f"/api/relay/{relay_id}/{'on' if state else 'off'}")

    async def set_all(self, state: bool) -> dict:
        return await self._request("POST", f"/api/relays/all/{'on' if state else 'off'}")