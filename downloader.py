import os
import asyncio
import random
import tempfile
import base64
import urllib.request
import yt_dlp

from proxy import proxy_manager

# Render jaisa host ephemeral disk deta hai — system temp dir use karna safe hai,
# OS khud isko manage/clean karta hai.
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", os.path.join(tempfile.gettempdir(), "yt-downloads"))
COOKIE_DIR = os.path.join(tempfile.gettempdir(), "yt-cookies")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _fetch_cookie_url(url: str) -> bytes | None:
    """Cookie URL (jaise batbin.me raw link) se content fetch karo."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as e:
        print(f"[cookies] URL fetch failed ({url}): {e}")
        return None


def _load_cookies_from_env():
    """
    Cookies repo mein commit nahi hoti — do tareeke support karta hai:

    1. COOKIE_URL1 / COOKIE_URL2 (...) — batbin.me jaisi jagah se raw
       cookie file ka direct link. Startup pe fetch karke temp dir mein
       save hoti hai.
    2. COOKIE_ACCOUNT1 / COOKIE_ACCOUNT2 (...) — base64-encoded content,
       agar URL use nahi karna.

    Dono ek saath bhi chal sakte hain (jitne mile utne accounts load honge).
    """
    os.makedirs(COOKIE_DIR, exist_ok=True)
    loaded = 0

    # Tareeka 1: URL se fetch
    i = 1
    while True:
        key = f"COOKIE_URL{i}"
        url = os.getenv(key)
        if not url:
            break
        content = _fetch_cookie_url(url)
        if content:
            path = os.path.join(COOKIE_DIR, f"url_account{i}.txt")
            with open(path, "wb") as f:
                f.write(content)
            loaded += 1
        i += 1

    # Tareeka 2: base64 env var se
    i = 1
    while True:
        key = f"COOKIE_ACCOUNT{i}"
        b64_content = os.getenv(key)
        if not b64_content:
            break
        try:
            decoded = base64.b64decode(b64_content)
            path = os.path.join(COOKIE_DIR, f"b64_account{i}.txt")
            with open(path, "wb") as f:
                f.write(decoded)
            loaded += 1
        except Exception as e:
            print(f"[cookies] {key} decode failed: {e}")
        i += 1

    print(f"[cookies] {loaded} cookie file(s) load hui.")


_load_cookies_from_env()


def get_cookie_file() -> str | None:
    """cookies/ folder se random .txt file pick karo"""
    if not os.path.exists(COOKIE_DIR):
        return None
    files = [f for f in os.listdir(COOKIE_DIR) if f.endswith(".txt")]
    return os.path.join(COOKIE_DIR, random.choice(files)) if files else None


def _build_opts(video_id: str, video: bool, proxy_url: str, cookie: str | None) -> dict:
    ext = "mp4" if video else "mp3"
    outtmpl = f"{DOWNLOAD_DIR}/{video_id}.{ext}"

    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "nocheckcertificate": True,
        "proxy": proxy_url,
        "socket_timeout": 30,
        "retries": 3,
        # Deno ka path — signature/n-challenge solving ke liye zaroori.
        # Agar Deno installed nahi hai to yt-dlp sirf image formats dega
        # aur audio/video "Requested format is not available" error dega.
        "js_runtimes": {"deno": {"path": os.getenv("DENO_PATH", "deno")}},
        # Deno hone ke bawajood yt-dlp ko ek "challenge solver script" (EJS)
        # bhi chahiye jo GitHub se remote fetch hoti hai. Iske bina Deno
        # silently skip ho jata hai aur signature solving fail hoti hai.
        "remote_components": ["ejs:github"],
        # ffmpeg ka path — audio ko mp3 mein convert karne ke liye zaroori.
        # Agar ye galat/missing ho to "Postprocessing: audio conversion failed" error aata hai.
        "ffmpeg_location": os.getenv("FFMPEG_PATH", "ffmpeg"),
    }

    if cookie:
        opts["cookiefile"] = cookie

    if video:
        opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        opts["merge_output_format"] = "mp4"
    else:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    return opts


async def download_track(video_id: str, video: bool = False) -> str | None:
    """
    Video ID se track download karo.
    Returns: file path on success, None on failure.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"

    def _cleanup_partial(vid: str):
        """Failed attempt ke baad us video_id ki koi bhi partial/leftover file hataye."""
        if not os.path.isdir(DOWNLOAD_DIR):
            return
        for fname in os.listdir(DOWNLOAD_DIR):
            if fname.startswith(vid):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, fname))
                except Exception:
                    pass

    def _attempt(cookie: str | None):
        proxy = proxy_manager.get_next()
        opts = _build_opts(video_id, video, proxy["ytdlp"], cookie)
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                path = ydl.prepare_filename(info)

                # Audio postprocess ke baad extension mp3 hoti hai
                if not video:
                    base = os.path.splitext(path)[0]
                    mp3_path = f"{base}.mp3"
                    if os.path.exists(mp3_path):
                        return mp3_path

                return path if os.path.exists(path) else None
            except Exception as e:
                print(f"[yt-dlp] Error: {e} | Cookie: {cookie} | Proxy: {proxy['url']}")
                _cleanup_partial(video_id)
                return None

    def _run():
        cookie = get_cookie_file()
        result = _attempt(cookie)
        if result:
            return result

        # Pehla attempt fail — agar cookie expired ho sakta hai,
        # cookie ke bina ek retry karo (kai baar bina cookie bhi kaam ho jata hai)
        if cookie is not None:
            print("[yt-dlp] Retrying without cookie...")
            result = _attempt(None)

        if not result:
            _cleanup_partial(video_id)

        return result

    return await asyncio.to_thread(_run)
