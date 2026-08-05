# Jarvis

A voice-controlled desktop assistant for macOS. Say the wake word, then
speak a command — Jarvis figures out what you want and actually does it:
opens apps, manages files, controls system settings, or runs a raw shell
command if nothing else fits. Comes with a local Claude-styled web UI as
an alternative to talking to a terminal.

## What it can do

- Open/quit apps, open URLs, search the web
- Find files (Spotlight), open/reveal/move files, list directories
- Volume, screenshots, lock screen, sleep, battery status, process list/kill
- Run arbitrary shell commands (the "full access" escape hatch)

## Brains

Jarvis's reasoning ("what tool do I call for this request?") is pluggable,
set via `BRAIN` in `.env`:

- **`claude`** — Anthropic's Claude, via API (`ANTHROPIC_API_KEY` required).
- **`hermes`** — [Nous Research Hermes](https://nousresearch.com/), running
  locally through [Ollama](https://ollama.com) (`ollama pull hermes3`, then
  `ollama serve`). No API key, no data leaving your machine, but needs a
  reasonably powerful Mac to run well.
- **`intents`** — a small built-in keyword matcher, no AI required.
- **`auto`** (default) — Claude if a key is set, otherwise Hermes, otherwise
  the keyword fallback.

Both `claude` and `hermes` use the exact same tool set in
`jarvis/brain/tools.py`, so switching brains doesn't change what Jarvis
can do — just which model is deciding how to do it.

## Web UI

`python -m jarvis.main --ui` opens a local Claude-styled chat window
(`localhost:5050`) instead of the terminal voice loop: a chat panel, a
status pill showing which brain/wake-word is active, a "Start listening"
toggle to turn the mic on/off from the browser, and a live tail of
`jarvis/logs/commands.log`. By default it only binds to localhost — nothing
is exposed to the network. In UI mode, risky shell commands can only be
confirmed while voice listening is active (there's no other channel to
ask through), so with the mic off they're declined automatically.

### Controlling it from your phone

Jarvis itself has to keep running on your Mac — it's the Mac that actually
opens apps, takes screenshots, runs shell commands, etc. Your phone just
connects to its web UI. Two ways to do that:

**`--public` (recommended, works anywhere):**
```bash
brew install cloudflared      # one-time
python -m jarvis.main --ui --public
```
This opens a free [Cloudflare quick tunnel](https://developers.cloudflare.com/pages/configuration/serving-pages/#dev-server) —
no account needed — and prints a real link:
```
[jarvis] Tap this link on your phone (works on any network, not just WiFi): https://random-words-1234.trycloudflare.com
[jarvis]   Password: 8f3k2n...
```
Tap that link on your phone from *anywhere* — cellular data, a different
WiFi, doesn't matter — since it's a normal internet connection, not
something that depends on both devices sharing a network. This sidesteps
every WiFi headache (client isolation, firewalls, wrong IPs) because
there's no LAN involved at all. The link is random and stops working the
moment you quit Jarvis, but **treat it like a password while it's live**
— anyone who gets the link can reach the login prompt for your Mac. Don't
post it, screenshot-share it, or leave it in a public chat.

**`--lan` (same-WiFi only, no extra install):**
```bash
python -m jarvis.main --ui --lan
```
Prints a `http://192.168.x.x:5050`-style link that only works when your
phone is on the exact same WiFi network as the Mac. See
[Troubleshooting phone access](#troubleshooting-phone-access) below if
that doesn't load.

Both require a password (HTTP Basic Auth) — auto-generated fresh each run,
or set `JARVIS_UI_TOKEN` in `.env` for a fixed one. Without it, anyone who
reaches the link (on your network for `--lan`, or anyone with the URL for
`--public`) could run shell commands on your Mac.

### Troubleshooting phone access

"UI running, but the phone can't load the page" is a networking problem
between the two devices, not a Jarvis bug. In rough order of likelihood:

1. **Different networks.** Phone and Mac must be on the *same* WiFi
   network. Check for: phone on cellular data with WiFi off, phone/Mac on
   different bands that show as separate networks (`Home` vs `Home-5G`),
   or one of them connected to a guest network.
2. **Client isolation.** Many networks — school/office WiFi especially,
   and increasingly home mesh routers and guest networks — deliberately
   block devices on the same WiFi from reaching each other, precisely to
   stop this kind of thing. If you're at school, this is the most likely
   cause and there's no workaround short of a network you control. Test
   on home WiFi to confirm.
3. **macOS Firewall.** System Settings → Network → Firewall. If it's on,
   click Options and make sure "Block all incoming connections" is off,
   and allow incoming connections for Python when prompted.
4. **VPN.** If the Mac is on a VPN, disconnect it — VPNs often route all
   traffic through a tunnel interface and can block LAN access entirely,
   and can also throw off which IP is actually reachable.
5. **Wrong IP.** `python -m jarvis.main --ui --lan` now lists every
   network IP it finds, ranked with Wi-Fi/Ethernet first — if the top one
   doesn't work, try the others it prints. You can cross-check against
   System Settings → Network → Wi-Fi → Details → TCP/IP.
6. **Sanity check from the Mac itself**: run `curl -u x:<password>
   http://<the-ip>:5050/` in a second terminal. If that fails too, it's
   not a phone problem — the server isn't actually reachable at that
   address.

### Installing it as an app on your phone

The UI is an installable PWA (manifest + icon + service worker), so it can
sit on your home screen and open in its own window instead of a browser
tab:

- **iOS (Safari)**: open the `--public` or `--lan` URL → Share button → **Add to Home Screen**.
- **Android (Chrome)**: open the URL → ⋮ menu → **Add to Home screen** / **Install app**.

Note that a `--public` link changes every run, so a home-screen icon
pointing at an old one will stop working next time — set `JARVIS_UI_TOKEN`
and consider `cloudflared tunnel` with a named/persistent tunnel (beyond
what's set up here) if you want a stable installed link.

It still needs your Mac reachable and Jarvis running —
installing it just changes how you launch and see it, not what it needs
to work. The service worker only caches the interface itself (HTML/CSS/JS)
so it opens instantly; every chat message and status check still talks
live to your Mac and won't work if it's asleep or off the network.

## Safety model

This gives an AI real control over your machine, so a few guardrails are
built in — they can all be relaxed via `.env`, they're just sane defaults:

- Every shell command Jarvis runs is logged to `jarvis/logs/commands.log`.
- Commands that look destructive (`rm -rf /`, `sudo`, `shutdown`, `dd`,
  `mkfs`, fork bombs, etc. — see `jarvis/safety.py`) trigger a spoken
  confirmation ("should I run it?") before executing.
- `ALLOW_SHELL=false` in `.env` disables raw shell access entirely, while
  keeping the structured app/file/system tools available.
- With no `ANTHROPIC_API_KEY` and no local Ollama/Hermes reachable, Jarvis
  falls back to a much more limited rule-based mode (open app, search,
  volume, battery, screenshot, lock, sleep) — no open-ended reasoning.

This is not a sandbox. Jarvis runs with your user's own permissions, so
treat it the way you'd treat a very literal, very fast intern with your
laptop password.

## Setup (macOS)

1. Install system audio deps (needed for `PyAudio`):
   ```bash
   brew install portaudio
   ```
2. Install Python deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the env template and fill in your Anthropic API key (skip this if
   you're only using Hermes):
   ```bash
   cp .env.example .env
   ```
4. For Hermes instead of/alongside Claude, install [Ollama](https://ollama.com)
   and pull a model:
   ```bash
   ollama pull hermes3
   ollama serve
   ```
5. Grant permissions the first time you run it:
   - **Microphone**: System Settings → Privacy & Security → Microphone → allow Terminal (or your IDE)
   - **Accessibility**: System Settings → Privacy & Security → Accessibility → allow Terminal (needed for lock-screen keystroke + some `osascript` actions)
6. (Optional, for phone access) `brew install cloudflared`
7. Run it:
   ```bash
   python -m jarvis.main             # voice loop in the terminal
   python -m jarvis.main --ui        # Claude-styled web chat at localhost:5050
   python -m jarvis.main --ui --public  # + a tap-anywhere phone link
   python -m jarvis.main --text      # plain terminal REPL, no mic needed
   ```
   In voice mode, say "Jarvis" and wait for it to respond before speaking
   your command.

## Project layout

```
jarvis/
  main.py           entrypoint: wake-word loop / text REPL / web UI
  config.py         env-driven settings
  safety.py         dangerous-command detection + logging
  audio/
    listener.py     wake word + speech-to-text
    speaker.py      text-to-speech (macOS `say`)
  actions/
    apps.py         open/quit apps, open URLs, web search
    files.py        find/open/move files, list dirs
    system.py       volume, screenshots, lock/sleep, battery, processes
    shell.py        raw shell command execution
  brain/
    llm.py          Claude tool-calling agent loop
    hermes.py        Hermes (Ollama) tool-calling agent loop
    intents.py       keyword-based fallback (no AI)
    tools.py         tool schemas + dispatch table, shared by all brains
  ui/
    app.py           Flask app: chat/status/logs/voice-toggle endpoints
    tunnel.py        cloudflared quick-tunnel for --public
    static/          Claude-styled HTML/CSS/JS front end
```

## Extending it

New capability = new function in `jarvis/actions/`, a matching entry in
`jarvis/brain/tools.py` (`TOOLS` schema + `DISPATCH` mapping), and
optionally a keyword pattern in `jarvis/brain/intents.py` for the
no-API-key fallback.
