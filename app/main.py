import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.api.routes import auth, devices, users
from app.core.config import settings
from app.core.security import hash_password
from app.db.models import User, UserRole
from app.db.session import SessionLocal, init_db
from app.services.discovery import discover_and_save
from app.services.poller import poll_all

WEB_DIR = Path(__file__).parent / "web"


async def ensure_admin() -> None:
    async with SessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(User))).scalar()
        if count == 0:
            db.add(User(username=settings.admin_username,
                        password_hash=hash_password(settings.admin_password),
                        role=UserRole.admin))
            await db.commit()
            print(f"Создан администратор '{settings.admin_username}' — смените пароль!")


async def discovery_loop() -> None:
    while True:
        try:
            n = await discover_and_save()
            print(f"Discovery: найдено {n} контроллеров")
        except Exception as e:
            print("Discovery error:", e)
        await asyncio.sleep(settings.scan_interval_seconds)


async def poll_loop() -> None:
    while True:
        await asyncio.sleep(settings.poll_interval_seconds)
        try:
            await poll_all()
        except Exception as e:
            print("Poll error:", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path("data").mkdir(exist_ok=True)
    await init_db()
    await ensure_admin()
    tasks = [asyncio.create_task(discovery_loop()), asyncio.create_task(poll_loop())]
    yield
    for t in tasks:
        t.cancel()
        with suppress(asyncio.CancelledError):
            await t


app = FastAPI(title="Smart Sockets Hub", version="1.0.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(devices.router)

app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/login", include_in_schema=False)
async def login_page():
    return FileResponse(WEB_DIR / "login.html")


@app.get("/", include_in_schema=False)
async def index_page():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return FileResponse(WEB_DIR / "admin.html")