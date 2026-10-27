from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import models
from .auth import require_auth
from .database import Base, engine
from .routers import admin, auth, cars, members, reservations

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="予約アプリ",
    description="学生マンションやシェアハウスで車を共有するための予約管理アプリ",
    version="1.0.0",
)

app.include_router(auth.router, prefix="/api")
app.include_router(
    cars.router, prefix="/api", dependencies=[Depends(require_auth)]
)
app.include_router(
    members.router, prefix="/api", dependencies=[Depends(require_auth)]
)
app.include_router(
    reservations.router, prefix="/api", dependencies=[Depends(require_auth)]
)
app.include_router(
    admin.router, prefix="/api", dependencies=[Depends(require_auth)]
)


@app.get("/api/health", tags=["システム"])
def health():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/manifest.json", include_in_schema=False)
def manifest():
    return FileResponse(
        STATIC_DIR / "manifest.json",
        media_type="application/manifest+json",
    )


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        STATIC_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache",
        },
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "icons" / "icon-192.png")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(STATIC_DIR / "index.html")
