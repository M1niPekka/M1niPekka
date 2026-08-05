"""Open/quit apps and websites."""

import subprocess
import webbrowser


def open_app(name: str) -> str:
    result = subprocess.run(["open", "-a", name], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Couldn't open {name}: {result.stderr.strip()}"
    return f"Opened {name}."


def quit_app(name: str) -> str:
    script = f'tell application "{name}" to quit'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Couldn't quit {name}: {result.stderr.strip()}"
    return f"Quit {name}."


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}."


def search_web(query: str) -> str:
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    webbrowser.open(url)
    return f"Searching the web for {query}."
