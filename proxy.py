import os
import itertools
import threading


def _load_proxy_list() -> list[str]:
    """
    PROXY_LIST env var se proxies load karo.
    Format: comma-separated "ip:port:user:pass" entries.
    Example env value:
      31.59.20.176:6754:user:pass,45.38.107.97:6014:user:pass
    """
    raw = os.getenv("PROXY_LIST", "")
    entries = [p.strip() for p in raw.split(",") if p.strip()]
    return entries


class ProxyManager:
    def __init__(self):
        proxies = _load_proxy_list()
        if not proxies:
            raise RuntimeError(
                "PROXY_LIST env var set nahi hai ya khaali hai. "
                "Format: ip:port:user:pass,ip:port:user:pass,..."
            )
        self._cycle = itertools.cycle(proxies)
        self._lock = threading.Lock()

    def get_next(self) -> dict:
        """Round-robin se agle proxy ka dict return karo"""
        with self._lock:
            raw = next(self._cycle)

        ip, port, user, password = raw.split(":")
        proxy_url = f"http://{user}:{password}@{ip}:{port}"

        return {
            "url": proxy_url,           # aiohttp ke liye
            "ytdlp": proxy_url,         # yt-dlp ke liye
        }


# Global instance — ek hi jagah se sab use karein
proxy_manager = ProxyManager()
