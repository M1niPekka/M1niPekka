"""Optional public HTTPS link via a Cloudflare "quick tunnel" -- gives Jarvis
a real https://*.trycloudflare.com URL that works from any network, since
it's just an outbound HTTPS connection from the Mac rather than something a
phone has to reach over local WiFi. No account or signup needed. The link is
random and only lives as long as this process does -- a fresh one is issued
every run.

Requires the `cloudflared` binary (`brew install cloudflared`); this module
only shells out to it, nothing here talks to Cloudflare directly.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading

_URL_RE = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")


def start_quick_tunnel(port: int, timeout: float = 20.0) -> tuple[subprocess.Popen | None, str | None]:
    """Starts the tunnel and waits (up to `timeout` seconds) for its public
    URL to show up in its output. Returns (process, url):
    - (None, None) if `cloudflared` isn't installed.
    - (process, None) if it started but no URL was parsed out in time --
      the caller should still terminate `process`.
    - (process, url) on success.
    """
    if shutil.which("cloudflared") is None:
        return None, None

    process = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    found = {"url": None}
    done = threading.Event()

    def _watch_output() -> None:
        for line in process.stdout:
            match = _URL_RE.search(line)
            if match:
                found["url"] = match.group(0)
                done.set()
                return

    threading.Thread(target=_watch_output, daemon=True).start()
    done.wait(timeout)
    return process, found["url"]
