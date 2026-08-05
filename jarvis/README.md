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
`jarvis/logs/commands.log`. It runs entirely on localhost — nothing is
exposed to the network. In UI mode, risky shell commands can only be
confirmed while voice listening is active (there's no other channel to
ask through), so with the mic off they're declined automatically.

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
6. Run it:
   ```bash
   python -m jarvis.main          # voice loop in the terminal
   python -m jarvis.main --ui     # Claude-styled web chat at localhost:5050
   python -m jarvis.main --text   # plain terminal REPL, no mic needed
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
    static/          Claude-styled HTML/CSS/JS front end
```

## Extending it

New capability = new function in `jarvis/actions/`, a matching entry in
`jarvis/brain/tools.py` (`TOOLS` schema + `DISPATCH` mapping), and
optionally a keyword pattern in `jarvis/brain/intents.py` for the
no-API-key fallback.
