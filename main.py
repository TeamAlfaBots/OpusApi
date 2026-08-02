import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from downloader import download_track, DOWNLOAD_DIR

# ── API Keys ─────────────────────────────────────────────────
# .env se load hoga (ya seedha yahan add karo)
API_KEYS: set[str] = set(
    filter(None, os.getenv("API_KEYS", "").split(","))
)

# Agar .env set nahi toh default dev key
if not API_KEYS:
    API_KEYS = {"alfabots-dev-key-change-this"}
# ─────────────────────────────────────────────────────────────


# ── Auth ──────────────────────────────────────────────────────
async def verify_key(api_key: str = Query(..., alias="api_key")):
    if api_key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
# ─────────────────────────────────────────────────────────────


# ── App ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    # Cookies ab COOKIE_ACCOUNT1/2/... env vars se downloader.py import
    # hote hi automatically decode + setup ho jaati hain.

    # Startup pe downloads folder clean karo — pichhle crash/restart
    # se koi leftover file na reh jaye (disk-full jaisa issue rokta hai).
    for fname in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, fname))
        except Exception:
            pass

    yield

app = FastAPI(
    title="AlfaBots YT Download API",
    version="1.0.0",
    lifespan=lifespan,
)
# ─────────────────────────────────────────────────────────────


# ── Routes ───────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "service": "AlfaBots YT API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/download")
async def download(
    url: str = Query(..., description="YouTube video URL"),
    type: str = Query("audio", description="audio ya video"),
    _key: str = Depends(verify_key),
):
    """
    YouTube se track download karke seedha stream karo.
    Stream complete hone ke baad file auto-delete ho jaati hai.
    """

    # Video ID extract karo
    video_id = _extract_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    is_video = type.lower() == "video"

    # Download karo
    filepath = await download_track(video_id, video=is_video)

    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=500, detail="Download failed")

    filename = os.path.basename(filepath)
    media_type = "video/mp4" if is_video else "audio/mpeg"

    # Stream + auto delete
    return AutoDeleteFileResponse(
        path=filepath,
        filename=filename,
        media_type=media_type,
    )


# ─────────────────────────────────────────────────────────────


# ── Auto-Delete File Response ─────────────────────────────────
class AutoDeleteFileResponse(FileResponse):
    """File stream karo aur baad mein delete karo"""

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                if os.path.exists(self.path):
                    os.remove(self.path)
                    print(f"[cleanup] Deleted: {self.path}")
            except Exception as e:
                print(f"[cleanup] Error deleting {self.path}: {e}")
# ─────────────────────────────────────────────────────────────


# ── Helper ───────────────────────────────────────────────────
import re

_YT_REGEX = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)

def _extract_id(url: str) -> str | None:
    match = _YT_REGEX.search(url)
    return match.group(1) if match else None
# ─────────────────────────────────────────────────────────────
