# Jarvis

A voice-controlled desktop assistant for macOS. Say the wake word, then
speak a command — Jarvis uses Claude to figure out what you want and
actually does it: opens apps, manages files, controls system settings,
or runs a raw shell command if nothing else fits.

## What it can do

- Open/quit apps, open URLs, search the web
- Find files (Spotlight), open/reveal/move files, list directories
- Volume, screenshots, lock screen, sleep, battery status, process list/kill
- Run arbitrary shell commands (the "full access" escape hatch)

## Safety model

This gives an AI real control over your machine, so a few guardrails are
built in — they can all be relaxed via `.env`, they're just sane defaults:

- Every shell command Jarvis runs is logged to `jarvis/logs/commands.log`.
- Commands that look destructive (`rm -rf /`, `sudo`, `shutdown`, `dd`,
  `mkfs`, fork bombs, etc. — see `jarvis/safety.py`) trigger a spoken
  confirmation ("should I run it?") before executing.
- `ALLOW_SHELL=false` in `.env` disables raw shell access entirely, while
  keeping the structured app/file/system tools available.
- Without `ANTHROPIC_API_KEY` set, Jarvis runs in a much more limited
  rule-based mode (open app, search, volume, battery, screenshot, lock,
  sleep) — no shell access, no open-ended reasoning.

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
3. Copy the env template and fill in your Anthropic API key:
   ```bash
   cp .env.example .env
   ```
4. Grant permissions the first time you run it:
   - **Microphone**: System Settings → Privacy & Security → Microphone → allow Terminal (or your IDE)
   - **Accessibility**: System Settings → Privacy & Security → Accessibility → allow Terminal (needed for lock-screen keystroke + some `osascript` actions)
5. Run it:
   ```bash
   python -m jarvis.main
   ```
   Then say "Jarvis" and wait for it to respond before speaking your command.

   To test without a microphone:
   ```bash
   python -m jarvis.main --text
   ```

## Project layout

```
jarvis/
  main.py           entrypoint: wake-word loop / text REPL
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
    intents.py       keyword-based fallback (no API key)
    tools.py         tool schemas + dispatch table
```

## Extending it

New capability = new function in `jarvis/actions/`, a matching entry in
`jarvis/brain/tools.py` (`TOOLS` schema + `DISPATCH` mapping), and
optionally a keyword pattern in `jarvis/brain/intents.py` for the
no-API-key fallback.
