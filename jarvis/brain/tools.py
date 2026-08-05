"""Maps Claude tool-use calls to the functions in jarvis/actions/."""

from jarvis.actions import apps, files, shell, system

TOOLS = [
    {
        "name": "open_app",
        "description": "Launch a macOS application by name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "App name, e.g. 'Spotify'"}},
            "required": ["name"],
        },
    },
    {
        "name": "quit_app",
        "description": "Quit a running macOS application by name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "open_url",
        "description": "Open a URL in the default browser.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the web for a query in the default browser.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "find_files",
        "description": "Search the filesystem (Spotlight) for files/folders matching a query.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "open_path",
        "description": "Open a file or folder at a given path with its default app.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "reveal_in_finder",
        "description": "Reveal a file or folder in Finder.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": "List the contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Defaults to home directory."}},
            "required": [],
        },
    },
    {
        "name": "move_file",
        "description": "Move or rename a file/folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["source", "destination"],
        },
    },
    {
        "name": "set_volume",
        "description": "Set system output volume, 0-100.",
        "input_schema": {
            "type": "object",
            "properties": {"level": {"type": "integer"}},
            "required": ["level"],
        },
    },
    {
        "name": "get_volume",
        "description": "Get the current system output volume.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "take_screenshot",
        "description": "Take a screenshot and save it to disk.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "lock_screen",
        "description": "Lock the screen immediately.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "sleep_mac",
        "description": "Put the Mac to sleep immediately.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_battery",
        "description": "Get battery percentage and charging status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_processes",
        "description": "List the top running processes by CPU usage.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "kill_process",
        "description": "Kill a process by name or PID.",
        "input_schema": {
            "type": "object",
            "properties": {"name_or_pid": {"type": "string"}},
            "required": ["name_or_pid"],
        },
    },
    {
        "name": "run_shell_command",
        "description": (
            "Run an arbitrary shell command on the user's Mac and return its output. "
            "Use this as a last resort for anything not covered by the other tools. "
            "The user has explicitly granted full shell access."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
]

DISPATCH = {
    "open_app": lambda i: apps.open_app(i["name"]),
    "quit_app": lambda i: apps.quit_app(i["name"]),
    "open_url": lambda i: apps.open_url(i["url"]),
    "search_web": lambda i: apps.search_web(i["query"]),
    "find_files": lambda i: files.find_files(i["query"]),
    "open_path": lambda i: files.open_path(i["path"]),
    "reveal_in_finder": lambda i: files.reveal_in_finder(i["path"]),
    "list_dir": lambda i: files.list_dir(i.get("path", "~")),
    "move_file": lambda i: files.move_file(i["source"], i["destination"]),
    "set_volume": lambda i: system.set_volume(i["level"]),
    "get_volume": lambda i: system.get_volume(),
    "take_screenshot": lambda i: system.take_screenshot(),
    "lock_screen": lambda i: system.lock_screen(),
    "sleep_mac": lambda i: system.sleep_mac(),
    "get_battery": lambda i: system.get_battery(),
    "list_processes": lambda i: system.list_processes(),
    "kill_process": lambda i: system.kill_process(i["name_or_pid"]),
    "run_shell_command": lambda i: shell.run_command(i["command"]),
}
