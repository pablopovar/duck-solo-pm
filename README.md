# Duck

Duck is a filesystem-based project dashboard for solo project management.

Projects remain ordinary folders on disk. Duck adds a lightweight management layer through a `.pocket/` directory inside each configured project.

## Current capabilities

- Discover projects beneath a configurable projects directory.
- Initialize an existing folder as a Duck project.
- Display a Markdown dashboard for each project.
- Sort projects alphabetically, by recent activity, or by score.
- Edit selected project-management files through the built-in Markdown editor.
- Open a project folder in the desktop file manager.
- Open a terminal in a project folder.
- Keep project content independent from the Duck application.

## Project structure

A configured project has this basic structure:


example-project/
├── .pocket/
│   ├── config.md
│   ├── dashboard.md
│   ├── decisions.md
│   ├── manifesto.md
│   ├── status.md
│   └── stream.md
├── canvas.md
└── inbox.md
