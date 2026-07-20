# Duck SoloPM

**A local-first project workspace built for one person.**

Duck gives a solo operator one place to see a project's context, record what happened, keep the next work visible, reach its resources, and ask questions grounded in the project itself.

It is not a team platform reduced to a single-user plan. There are no roles to assign, teammates to invite, Gantt charts to maintain, or workflows to sell to anyone else.

Duck starts with a simpler requirement: open a project and understand it quickly.

## Why Duck exists

Projects rarely live in one application. Their working reality is spread across folders, repositories, documents, notes, links, browser tabs, terminals, and conversations.

Duck keeps the Local Folder as the project and adds a compact management layer around it:

- a fast project overview;
- direct access to folders, repositories, terminals, and important resources;
- one chronological stream for Notes, Todos, Statuses, Links, and Files;
- project-level and system-wide model chat grounded in stored project evidence;
- local state that remains with the project instead of living in a remote service.

## What Duck currently does

### Project workspace

Each configured project has three focusable columns:

1. **Project** — About, Quick Links, pinned resources, and the top three open Todos.
2. **Activity** — the project's chronological stream of Notes, Todos, Statuses, Links, and Files.
3. **Chat** — a project assistant that can search and read the project's files.

Columns can be collapsed, normalized, expanded, reordered, and grouped into collapsed stacks. Focusing one column gives it the available working space and collapses the others.

The Activity feed supports:

- collapsed, compact entries;
- filtering by activity type;
- titles for every item;
- multiline Notes and Todos without the former 2,000-character limit;
- completion state for Todos;
- soft deletion of activity items;
- three persistent interface densities: Spacious, Standard, and Compact;
- a pop-up composer that stays out of the workspace until needed.

### Files and resources

Duck can:

- upload a file into the project's `files/` directory;
- create a Markdown file from text entered in the browser;
- download a file through the project interface;
- convert a Note into a file—the item ceases to be a Note;
- pin Links and Files into the project's Pinned Resources block;
- refuse unsafe paths and avoid silently overwriting an existing file.

Duck's file model is intentionally direct: **the files in Duck are the files in the Local Folder.** It does not create a parallel document store.

### Project context

Project context includes:

- an editable About profile: what the project is, why it exists, and its class;
- configurable Status, Category, Priority, Class, and Type values;
- Current State, Next Action, Unresolved Decisions, and Milestone Definition fields;
- configurable project score and resource links;
- optional leave-project and periodic reminders.

Desktop links can open the project folder, a terminal at the project path, the local repository, and GitHub. These actions require Duck's desktop protocol handler on the computer running the browser.

## Model chat

Duck works with an OpenAI-compatible model API. It can use a local Ollama endpoint, the OpenAI API, or another compatible service.

### Project chat

Project chat operates inside one project. Duck builds a readable-file inventory and exposes three model tools:

- `list_project_files`
- `search_project_files`
- `read_project_file`

The model receives the inventory, chooses what to search or read, and answers from the returned evidence. Responses are instructed to cite project paths and distinguish stored evidence from inference.

Duck reads UTF-8-compatible text and extracts text from PDFs. It excludes dependency trees and internal material such as `.git`, `.venv`, `node_modules`, Python caches, database files, backups, binary files, and symlinks.

SQLite-backed About data, settings, Notes, Todos, Links, Files, and Activity are exposed to project chat through the virtual path:

```text
.duck/project-data.json
```

The current project-chat tools are read-only. They do not let the model modify project files.

### System-wide chat

The main dashboard at `/` contains **Ask Duck**, a persistent chat operating across all configured projects.

It can inspect:

- project identities and About profiles;
- project settings and qualifiers;
- Notes, Todos, Statuses, Links, and File metadata;
- pinned resources;
- recent Activity;
- open Todos;
- matching Activity across projects.

System-wide chat deliberately does **not** read arbitrary Local Folder file contents. Project file reading belongs to the chat inside that project.

## Storage model

Projects remain ordinary folders under one configured projects directory. Duck discovers immediate child folders and can initialize an existing folder as a Duck project.

A representative configured project looks like this:

```text
projects/
├── .duck/
│   └── system.sqlite3
└── example-project/
    ├── .duck/
    │   ├── project.sqlite3
    │   ├── config.md
    │   ├── dashboard.md
    │   ├── project-settings.json
    │   ├── session-values.json
    │   └── ...
    ├── files/
    ├── inbox.md
    ├── canvas.md
    └── the rest of the project
```

The per-project SQLite database is the canonical store for Activity, the About profile, project settings, and project chat history. System chat history and the project registry live in `PROJECTS_ROOT/.duck/system.sqlite3`.

`.duck/` is the canonical Duck system directory. Projects that still contain only `.pocket/` remain readable but display a legacy warning and an explicit migration action. If both directories exist, Duck reports a conflict instead of guessing.

## Requirements

- Docker
- Docker Compose
- a directory containing the project folders Duck should see
- a modern browser
- optionally, an OpenAI-compatible model service
- optionally, the desktop protocol handler for local folder and terminal actions

## Installation

Clone the repository:

```bash
git clone https://github.com/pablopovar/duck-solo-pm.git
cd duck-solo-pm
```

Create the local environment file:

```bash
cp .env.dist .env
```

Edit `.env` with absolute host paths:

```dotenv
POCKET_PROJECTS_PATH="/absolute/path/to/projects"
POCKET_PROJECTS_HOST_PATH="/absolute/path/to/projects"
POCKET_PORT="3200"

DUCK_UID="1000"
DUCK_GID="1000"

DUCK_LEAVE_REMINDER_ENABLED="true"
DUCK_LEAVE_REMINDER_MESSAGE="Add a status update before leaving."

DUCK_PERIODIC_REMINDER_ENABLED="true"
DUCK_PERIODIC_REMINDER_MINUTES="60"
DUCK_PERIODIC_REMINDER_MESSAGE="Time to update the status."
```

The `POCKET_*` environment names are retained for compatibility with the project's earlier name. New project state is stored under `.duck/`.

Set `DUCK_UID` and `DUCK_GID` to the host user that owns the project folders:

```bash
id -u
id -g
```

This prevents the container from creating root-owned files in bind-mounted projects.

Build and start Duck:

```bash
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:3200/
```

Use the port configured by `POCKET_PORT` if it differs from `3200`.

## Model configuration

### Local Ollama

Duck's default endpoint is Ollama's OpenAI-compatible API on the host:

```dotenv
DUCK_MODEL_BASE_URL="http://host.docker.internal:11434/v1"
DUCK_MODEL_NAME=""
DUCK_MODEL_API_KEY=""
DUCK_MODEL_TIMEOUT_SECONDS="300"
```

Ollama must be reachable from the container, and the selected model must support reliable function/tool calling. Leaving `DUCK_MODEL_NAME` empty lets Duck choose from the models returned by the endpoint.

### OpenAI API

To use OpenAI directly:

```dotenv
DUCK_MODEL_BASE_URL="https://api.openai.com/v1"
DUCK_MODEL_NAME="gpt-4.1-nano"
DUCK_MODEL_API_KEY="your-api-key"
DUCK_MODEL_TIMEOUT_SECONDS="300"
```

`gpt-4.1-nano` is a low-cost development choice with function calling. Keep the API key only in `.env`; never commit it.

After changing model settings, recreate the container:

```bash
docker compose up -d --force-recreate
```

Duck currently uses one model endpoint and API key at a time. The model selector lists the models returned by that endpoint.

## Initializing a project

1. Create or place a project folder directly under the configured projects directory.
2. Open Duck.
3. Select the folder from the Projects list.
4. Choose to configure it.
5. Submit the configuration form. Its fields are optional.

Duck initializes the existing folder; it does not currently create new project folders or register arbitrary folders outside the configured projects root.

## Common operations

Start or rebuild after source changes:

```bash
docker compose up -d --build --force-recreate
```

Stop Duck:

```bash
docker compose down
```

Inspect the running service:

```bash
docker compose ps
```

Verify the container identity:

```bash
docker compose exec web id
```

## Current boundaries

Duck is under active development. The current implementation is intentionally narrow:

- single-user, with no application authentication or guest system;
- one configured projects root mounted into Docker;
- projects discovered as immediate child folders of that root;
- no arbitrary external project-folder registration yet;
- no project-folder creation from the Duck interface yet;
- one model provider endpoint at a time;
- system chat reads structured Duck data and Activity, not arbitrary files across every project;
- deleting a File activity record does not delete the physical file from the Local Folder;
- Activity deletion is soft deletion, but recovery is not yet exposed in the interface.

These are current implementation boundaries, not claims about Duck's eventual scope.

## Technology

- Python 3.13
- FastAPI and Uvicorn
- SQLite
- Jinja templates
- vanilla JavaScript and CSS
- Milkdown Crepe for the Markdown editor
- Docker Compose

## Name

The earlier working name was **Door to Pocket**. The decided name is **Duck SoloPM**—from *“Fuck, I don't have a name for this.”*

## License

Duck SoloPM is released under the GNU General Public License, version 3.

See [LICENSE](LICENSE).
