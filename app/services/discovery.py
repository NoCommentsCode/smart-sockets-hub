"""Скан локальной сети: TCP-проба порта +指纹 через /api/device/info.

Найденные контроллеры и их розетки сохраняются в БД (upsert по IP).
"""
import asyncio
import ipaddress
import socket
from datetime import datetime, timezone

from sqlalchemy import delete, select, update

from app.core.config import settings
from app.db.models import Controller, Relay
from app.db.session import SessionLocal
from app.services.device_client import DeviceClient, DeviceError


def get_scan_network() -> str:
    if settings.scan_cidr:
        return settings.scan_cidr
    # Определяем основной локальный IP (UDP-сокет ничего не отправляет)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()
    return str(ipaddress.ip_network(f"{local_ip}/24", strict=False))


async def _probe(ip: str, sem: asyncio.Semaphore) -> str | None:
    async with sem:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, settings.device_http_port), timeout=0.7
            )
            writer.close()
            return ip
        except (OSError, asyncio.TimeoutError):
            return None


async def _fingerprint_and_save(db, ip: str) -> bool:
    client = DeviceClient(ip)
    try:
        info = await client.get_info()
        relays_data = await client.get_relays()
    except DeviceError:
        return False  # порт открыт, но это не наша прошивка

    if "relays_count" not in info or "relays" not in relays_data:
        return False

    c = (await db.execute(select(Controller).where(Controller.ip == ip))).scalar_one_or_none()
    if not c:
        c = Controller(ip=ip)
        db.add(c)
    c.name = info.get("name", "")
    c.version = info.get("version", "")
    c.is_online = True
    c.last_seen = datetime.now(timezone.utc)
    await db.flush()

    existing = (await db.execute(select(Relay).where(Relay.controller_id == c.id))).scalars().all()
    by_id = {r.relay_id: r for r in existing}
    actual_ids = []
    for item in relays_data["relays"]:
        rid = int(item["id"])
        actual_ids.append(rid)
        r = by_id.get(rid)
        if not r:
            r = Relay(controller_id=c.id, relay_id=rid)
            db.add(r)
        r.name = item.get("name", "")
        r.state = bool(item.get("state", False))
    if actual_ids:
        await db.execute(delete(Relay).where(
            Relay.controller_id == c.id, Relay.relay_id.not_in(actual_ids)
        ))
    return True


async def discover_and_save() -> int:
    network = ipaddress.ip_network(get_scan_network(), strict=False)
    sem = asyncio.Semaphore(100)
    probes = await asyncio.gather(*(_probe(str(h), sem) for h in network.hosts()))
    open_ips = [ip for ip in probes if ip]

    found_ips = []
    async with SessionLocal() as db:
        for ip in open_ips:
            if await _fingerprint_and_save(db, ip):
                found_ips.append(ip)
        # Не найденные в этом скане контроллеры помечаем offline
        if found_ips:
            await db.execute(update(Controller).where(Controller.ip.not_in(found_ips)).values(is_online=False))
        else:
            await db.execute(update(Controller).values(is_online=False))
        await db.commit()
    return len(found_ips)