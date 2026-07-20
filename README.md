# Duck SoloPM

> I made Duck! to get quick clarity and fast pivoting across tons of ongoing projects—to fend off cognitive burn.

**A local-first project workspace built for one person.**

Duck gives a solo operator one place to see a project's context, record what happened, keep the next work visible, reach its resources, and ask questions using evidence Duck can retrieve from the project.

It is not a team platform reduced to a single-user plan. There are no roles to assign, teammates to invite, Gantt charts to maintain, or workflows to sell to anyone else.

Duck starts with a simpler requirement: open a project and understand it quickly.

## Why Duck exists

Projects rarely live in one application. Their working reality is spread across folders, repositories, documents, notes, links, browser tabs, terminals, and conversations.

The recurring cost is reorientation: finding the right project, recovering its context, reconstructing what changed, and locating the next action before work can resume. Duck exists to reduce that accumulated cognitive burn.

Duck keeps the Local Folder as the project and adds a compact management layer around it:

- a fast project overview;
- direct access to folders, repositories, terminals, and important resources;
- one chronological stream for Notes, Todos, Statuses, Links, and Files;
- project-level and system-wide model chat with tools for retrieving stored project evidence;
- project data stored locally with the project, plus system-wide state stored at the configured projects root.

Duck is local-first, not necessarily local-only. When a remote model provider is configured, conversation messages and the project evidence returned to the model are sent to that provider.

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
- soft deletion of activity items;
- three persistent interface densities: Spacious, Standard, and Compact;
- a pop-up composer that stays out of the workspace until needed.

The feed currently loads the latest 100 activity records. Pagination and a recovery interface for soft-deleted records are not implemented.

### Files and resources

Duck can:

- upload a file into the project's `files/` directory;
- create a Markdown file from text entered in the browser;
- download a file through the project interface;
- convert a Note into a file—the item ceases to be a Note;
- pin Links, Files, and existing Document activity items into the project's Pinned Resources block;
- refuse unsafe paths and avoid silently overwriting an existing file.

Duck's file model is intentionally direct: **the files in Duck are the files in the Local Folder.** It does not create a parallel document store.

### Project context and editor

The current project workspace includes:

- an editable About profile: what the project is, why it exists, and its class;
- configurable Status, Category, Priority, Class, and Type values;
- configurable project score and resource links;
- optional leave-project and periodic reminders.

The older project dashboard remains available at `/project/<slug>/legacy`. Its Markdown-backed project-state view includes Current State, Next Action, Unresolved Decisions, and Milestone Definition. It is retained for compatibility and is not the primary Activity workspace.

Duck also includes a built-in Markdown editor at `/project/<slug>/edit` for project Markdown files.

Desktop links can open the project folder, a terminal at the project path, the local repository, and GitHub. These actions require Duck's desktop protocol handler to be installed and registered on the computer running the browser.

## Model chat

Duck works with a model service that implements the parts of the OpenAI-compatible contract it currently uses: model discovery through `GET /models`, chat through `POST /chat/completions`, and OpenAI-style function/tool calls. It can use a local Ollama endpoint, the OpenAI API, or another service that implements those behaviors.

### Project chat

Project chat operates inside one project. At the start of a request, Duck walks the project and reads eligible files into the Duck server process to build a searchable inventory. The model receives the inventory manifest, not every file's complete contents, and can request content through three tools:

- `list_project_files`
- `search_project_files`
- `read_project_file`

The model is instructed to choose what to search or read, answer from returned evidence, cite project paths, and distinguish stored evidence from inference. Tool use and answer quality still depend on the selected model; Duck does not independently prove that every generated statement is supported.

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

The system chat exposes these tools to the model:

- `list_projects`
- `search_project_activity`
- `get_project_overview`
- `list_project_activity`
- `list_project_todos`
- `get_activity_item`

For a question naming one project, Duck requires a project overview before accepting the answer and performs one corrective retry when a small model stops after listing projects. This improves project resolution but does not guarantee a correct answer.

System-wide chat deliberately does **not** read arbitrary Local Folder file contents. Project file reading belongs to the chat inside that project.

System chat history is persistent and can be cleared from the interface. The main chat also provides Copy Answer and persistent text-size levels at 60%, 70%, 85%, 100%, 115%, 130%, and 145%. Those two interface features are not currently present in project chat.

The dashboard's project list can be sorted alphabetically, by recent activity, or by score.

## Storage model

Projects remain ordinary folders under one configured projects directory. Duck discovers immediate child folders and can initialize an existing folder as a Duck project.

A representative configured project looks like this:

```text
projects/
├── .duck/
│   └── system.sqlite3
└── example-project/
    ├── .duck/
    │   └── project.sqlite3
    ├── files/
    └── the project's ordinary files and folders
```

The per-project SQLite database is the canonical store for Activity, the About profile, project settings, and project chat history. System chat history and the project registry live in `PROJECTS_ROOT/.duck/system.sqlite3`.

Older projects may also contain Markdown, JSON, or JSONL files such as `config.md`, `dashboard.md`, `inbox.md`, `project-settings.json`, `session-values.json`, or `.pocket/activity.jsonl`. Their presence is project- and history-dependent; they are not all required parts of a newly configured project.

On first use of the SQLite activity store, Duck can import existing Notes, Links, Todos, and Statuses from the legacy Markdown and JSONL sources. The import is recorded so it is not repeated, and the original source files are left unchanged.

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

Create the local environment file. You may copy `.env.dist` as a starting point:

```bash
cp .env.dist .env
```

The current `.env.dist` lags the runtime configuration: it still shows port `8000` and does not list the model variables below. Use the values in this README when editing `.env`; Docker Compose itself defaults the application port to `3200`.

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

This configuration matches Duck's current HTTP client and OpenAI's compatible endpoints, but direct OpenAI operation has not been runtime-confirmed in the development record for this release.

After changing model settings, recreate the container:

```bash
docker compose up -d --force-recreate
```

Duck currently uses one model endpoint and API key at a time. The model selector lists the models returned by that endpoint.

When the endpoint is remote, Duck sends chat messages and any evidence returned through model tools to that service. Review the provider's data handling before using sensitive project material. A local Ollama endpoint keeps model inference local; selecting a remote Ollama cloud model does not.

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
- project chat scans and reads eligible project files in the Duck server process before exposing the inventory to model tools;
- the selected model may fail to call an appropriate tool or may generate an unsupported statement despite Duck's instructions;
- the Activity feed is limited to the latest 100 records and has no pagination;
- existing Activity items cannot yet be edited through the interface;
- Todos have a stored `completed` field, but the current interface and API do not provide an action for marking a Todo complete;
- deleting a File activity record does not delete the physical file from the Local Folder;
- Activity deletion is soft deletion, but recovery is not yet exposed in the interface;
- project chat does not yet have the system chat's Copy Answer control;
- the current repository does not include a dark theme.

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

The practical origin of Duck is the need for quick clarity and fast pivoting across tons of ongoing projects. The earlier working name was **Door to Pocket**. The decided name is **Duck SoloPM**—from *“Fuck, I don't have a name for this.”*

## License

Duck SoloPM is released under the GNU General Public License, version 3.

See [LICENSE](LICENSE).
