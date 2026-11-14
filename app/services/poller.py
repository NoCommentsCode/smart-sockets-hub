"""Периодический опрос статусов всех известных контроллеров."""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Controller, Relay
from app.db.session import SessionLocal
from app.services.device_client import DeviceClient, DeviceError


async def _poll_one(controller_id: int) -> None:
    async with SessionLocal() as db:
        c = await db.get(Controller, controller_id)
        if not c:
            return
        try:
            data = await DeviceClient(c.ip).get_relays()
        except DeviceError:
            c.is_online = False
            await db.commit()
            return

        relays = (await db.execute(select(Relay).where(Relay.controller_id == c.id))).scalars().all()
        by_id = {r.relay_id: r for r in relays}
        for item in data.get("relays", []):
            r = by_id.get(item["id"])
            if r:
                r.name = item.get("name", r.name)
                r.state = bool(item.get("state", False))
        c.is_online = True
        c.last_seen = datetime.now(timezone.utc)
        await db.commit()


async def poll_all() -> None:
    async with SessionLocal() as db:
        ids = (await db.execute(select(Controller.id))).scalars().all()
    # Отдельная сессия на контроллер — AsyncSession нельзя шарить между задачами
    await asyncio.gather(*(_poll_one(i) for i in ids), return_exceptions=True)