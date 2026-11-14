from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.models import Controller, Relay, User
from app.db.session import get_db
from app.schemas import ControllerOut, RelayOut, StateRequest
from app.services.device_client import DeviceClient, DeviceError
from app.services.discovery import discover_and_save
from app.services.poller import poll_all

router = APIRouter(prefix="/api", tags=["devices"])


@router.get("/controllers", response_model=list[ControllerOut])
async def list_controllers(user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Controller).order_by(Controller.id))).scalars().all()


@router.post("/refresh")
async def refresh(user: User = Depends(get_current_user)):
    await poll_all()
    return {"ok": True}


@router.post("/scan")
async def scan(admin: User = Depends(require_admin)):
    return {"found": await discover_and_save()}


@router.post("/relays/all")
async def set_all_relays(data: StateRequest, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    controllers = (await db.execute(select(Controller))).scalars().all()
    failed = []
    for c in controllers:
        try:
            await DeviceClient(c.ip).set_all(data.state)
            await db.execute(update(Relay).where(Relay.controller_id == c.id).values(state=data.state))
            c.is_online = True
        except DeviceError:
            c.is_online = False
            failed.append(c.ip)
    await db.commit()
    return {"ok": not failed, "failed": failed}


@router.post("/relays/{relay_pk}/state", response_model=RelayOut)
async def set_relay(relay_pk: int, data: StateRequest,
                    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    relay = await db.get(Relay, relay_pk)
    if not relay:
        raise HTTPException(404, "Розетка не найдена")
    c = await db.get(Controller, relay.controller_id)
    try:
        await DeviceClient(c.ip).set_relay(relay.relay_id, data.state)
    except DeviceError:
        c.is_online = False
        await db.commit()
        raise HTTPException(502, "Контроллер недоступен")
    relay.state = data.state
    c.is_online = True
    c.last_seen = datetime.now(timezone.utc)
    await db.commit()
    return relay


@router.post("/controllers/{controller_id}/all", response_model=dict)
async def set_controller_all(controller_id: int, data: StateRequest,
                             user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await db.get(Controller, controller_id)
    if not c:
        raise HTTPException(404, "Контроллер не найден")
    try:
        await DeviceClient(c.ip).set_all(data.state)
    except DeviceError:
        c.is_online = False
        await db.commit()
        raise HTTPException(502, "Контроллер недоступен")
    await db.execute(update(Relay).where(Relay.controller_id == c.id).values(state=data.state))
    c.is_online = True
    c.last_seen = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}

@router.delete("/controllers/{controller_id}", status_code=204)
async def delete_controller(controller_id: int,
                            admin: User = Depends(require_admin),
                            db: AsyncSession = Depends(get_db)):
    c = await db.get(Controller, controller_id)
    if not c:
        raise HTTPException(404, "Контроллер не найден")
    await db.delete(c)  # розетки удалятся каскадом
    await db.commit()