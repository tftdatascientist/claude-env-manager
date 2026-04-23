# Active Projects Tab — Design Spec

## Overview
New tab "Active Projects" in the main QTabWidget, allowing users to mark projects as active from History and browse their file trees.

## Marking projects as active
- Checkboxes on project-level items in History QTreeWidget
- State persisted in `active_projects.json` (list of resolved project paths)
- Checking/unchecking immediately updates Active Projects tab

## Tab layout
```
+------------------+----------------------------------+
| Lista aktywnych  | Drzewo plikow wybranego projektu |
| projektow        |                                  |
| (QListWidget)    | (QTreeView + QFileSystemModel)   |
|                  |                                  |
|   project-a  <-- |  project-a/                      |
|   project-b      |   src/                           |
|   ^selected      |     main.py                      |
|                  |   node_modules/  [gray]          |
|                  |   .git/          [gray]          |
|                  |   README.md                      |
|                  +----------------------------------+
|                  | Podglad pliku (QPlainTextEdit)   |
|                  | read-only, Consolas 10           |
+------------------+----------------------------------+
```

## Splitter proportions
- Left (project list) : Right = 1:3
- Right: file tree : preview = 3:1

## Special directory coloring
Gray (#808080) italic for: node_modules, .git, __pycache__, .venv, venv, .env, dist, build, .next, .cache, .tox, egg-info

## Interactions
- Single click on file in tree -> preview content in bottom panel (read-only)
- Double click on file -> os.startfile() (open in system default app)
- Right-click on file/folder -> Open in Explorer, Open in VS Code, Open terminal here, Copy path

## Keyboard shortcut
- Ctrl+3 to switch to Active Projects tab

## Files
- `src/ui/active_projects_panel.py` — new panel
- `active_projects.json` — persistence of active project list
- Modified: `src/ui/history_panel.py` — add checkboxes to project items
- Modified: `src/ui/main_window.py` — add third tab + Ctrl+3 shortcut
