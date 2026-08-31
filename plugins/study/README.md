# study

Study workflows for high school, built as a Claude Code plugin.

## Skills

| Skill | What it does |
|---|---|
| `exam-guide` | Builds a focused guide for a specific upcoming test. Adapts to time left — a night-before guide is mostly strategy and logistics; a two-weeks-out guide is content coverage. |
| `flashcards` | Turns notes, a chapter, or a vocab list into active-recall cards, then quizzes you one at a time and tracks what you miss. Exports to Anki/Quizlet CSV. |
| `study-plan` | Day-by-day schedule planned backwards from the test date, fitted around your real week. |
| `notes-to-studysheet` | Messy class notes, a whiteboard photo, or a chapter into a clean one-page study sheet. Flags gaps instead of silently filling them. |
| `due-check` | Pulls what's actually due from calendar, email, and files, and flags what's at risk. |

Skills trigger on their own when relevant — you don't have to call them by
name. "I have a bio test Thursday, help" will reach for `exam-guide`.

## Install

From the Claude Code CLI:

```
/plugin marketplace add M1niPekka/M1niPekka
/plugin install study@enzo-study
```

## Connectors worth having on

`due-check` reads from whatever is connected, and says what it couldn't see.
Google Calendar, Gmail, and Google Drive make it substantially more useful.
