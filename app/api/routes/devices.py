from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.models import Controller, Relay, User
from app.db.session import get_db
from app.schemas import (
    ControllerConfigOut,
    ControllerConfigUpdate,
    ControllerOut,
    RelayOut,
    StateRequest,
)
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


@router.get("/controllers/{controller_id}/config", response_model=ControllerConfigOut)
async def get_controller_config(controller_id: int,
                                user: User = Depends(get_current_user),
                                db: AsyncSession = Depends(get_db)):
    c = await db.get(Controller, controller_id)
    if not c:
        raise HTTPException(404, "Контроллер не найден")
    if not c.is_online:
        raise HTTPException(503, "Контроллер не в сети")
    try:
        return await DeviceClient(c.ip).get_config()
    except DeviceError as e:
        c.is_online = False
        await db.commit()
        raise HTTPException(502, f"Не удалось получить конфиг: {e}")


@router.patch("/controllers/{controller_id}/config", response_model=ControllerConfigOut)
async def update_controller_config(controller_id: int, data: ControllerConfigUpdate,
                                   user: User = Depends(get_current_user),
                                   db: AsyncSession = Depends(get_db)):
    c = await db.get(Controller, controller_id)
    if not c:
        raise HTTPException(404, "Контроллер не найден")
    if not c.is_online:
        raise HTTPException(503, "Контроллер не в сети")

    payload = {}
    if data.device_name is not None:
        payload["device_name"] = data.device_name.strip()
    if data.relays is not None:
        relays_payload = []
        for item in data.relays:
            relay_update = {"id": item.id}
            if item.name is not None:
                relay_update["name"] = item.name.strip()
            if item.default_state is not None:
                relay_update["default_state"] = item.default_state
            if len(relay_update) > 1:
                relays_payload.append(relay_update)
        if relays_payload:
            payload["relays"] = relays_payload

    if not payload:
        raise HTTPException(400, "Нет изменений для сохранения")

    try:
        updated = await DeviceClient(c.ip).update_config(payload)
    except DeviceError as e:
        raise HTTPException(502, f"Не удалось сохранить конфиг: {e}")

    c.name = updated["device_name"]
    relays = (await db.execute(select(Relay).where(Relay.controller_id == c.id))).scalars().all()
    by_id = {r.relay_id: r for r in relays}
    for item in updated["relays"]:
        relay = by_id.get(item["id"])
        if relay:
            relay.name = item["name"]
    c.last_seen = datetime.now(timezone.utc)
    await db.commit()
    return updated


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
    await db.delete(c)
    await db.commit()