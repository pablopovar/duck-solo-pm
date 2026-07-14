# Duck

Duck is a local, filesystem-first dashboard for solo project management.

Projects remain ordinary folders on disk. Duck adds a lightweight management layer through a `.pocket/` directory inside each configured project. It does not require a project database or fixed absolute paths.

## Current capabilities

- Discover project folders beneath one configurable projects directory.
- Initialize an existing folder as a Duck project.
- Display a Markdown dashboard for each project.
- Sort projects alphabetically, by recent activity, or by score.
- Edit selected project-management Markdown files in the built-in editor.
- Open a project folder in the desktop file manager.
- Open a terminal in a project folder.
- Open configured GitHub and local-repository locations.
- Request an optional one-line status update when leaving a project.
- Append submitted status updates to `.pocket/status.md` with a timestamp.
- Display configurable system-wide periodic reminders while Duck is open.
- Run the container under a configured host UID and GID to avoid root-owned project files.

## Project structure

A configured project has this basic structure:

```text
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
````

Duck recognizes a configured project through:

```text
.pocket/config.md
```

The project folder remains portable. Duck derives its location from the configured projects root rather than requiring a separate application database entry.

## Application structure

```text
duck-solo-pm/
├── app/
├── docs/
├── web/
├── .env.dist
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Requirements

* Docker
* Docker Compose
* A directory containing the projects Duck should manage
* A modern web browser

The **Open folder**, **Open terminal**, and local-repository controls require the Duck desktop protocol handler on the computer running the browser.

## Configuration

Create the local configuration from the distributable template:

```bash
cp .env.dist .env
```

Edit `.env`:

```dotenv
POCKET_PROJECTS_PATH="/path/to/projects"
POCKET_PROJECTS_HOST_PATH="/path/to/projects"
POCKET_PORT="3200"

DUCK_LEAVE_REMINDER_ENABLED="true"
DUCK_LEAVE_REMINDER_MESSAGE="Add a one-line status update before leaving."

DUCK_PERIODIC_REMINDER_ENABLED="true"
DUCK_PERIODIC_REMINDER_MINUTES="30"
DUCK_PERIODIC_REMINDER_MESSAGE="Time to update the status."

DUCK_UID="1000"
DUCK_GID="1000"
```

### Project paths

`POCKET_PROJECTS_PATH` is the directory mounted into the Duck container.

`POCKET_PROJECTS_HOST_PATH` is the corresponding host path used by desktop actions such as opening a folder or terminal.

For a local installation, these normally contain the same path.

### Port

`POCKET_PORT` controls the host port used to access Duck.

The default is:

```text
3200
```

### Container identity

`DUCK_UID` and `DUCK_GID` define the user and group under which Duck runs inside the container.

Set them to the UID and GID of the host user who owns the project folders. On many Linux systems, the first regular user is:

```dotenv
DUCK_UID="1000"
DUCK_GID="1000"
```

This prevents Duck from creating root-owned files in bind-mounted projects.

### Leave-project reminder

The leave-project reminder is global. It is not configured separately for each project.

When leaving a project, Duck can display a one-line status field. The update is optional. When submitted, Duck appends it to:

```text
.pocket/status.md
```

Example:

```markdown
- **07/14/2026 11:52 AM** — Finished the initial reminder implementation.
```

Pressing `Esc` closes the Duck reminder without submitting an update.

Duck may also show the custom reminder when the pointer exits through the top of the page as an exit-intent signal.

### Periodic reminder

The periodic reminder is also global.

It appears throughout Duck at the configured interval, regardless of which project is open. It runs only while Duck is open in the browser.

The interval is expressed in whole minutes:

```dotenv
DUCK_PERIODIC_REMINDER_MINUTES="30"
```

For testing every minute:

```dotenv
DUCK_PERIODIC_REMINDER_MINUTES="1"
```

After changing `.env`, recreate the container:

```bash
docker compose up -d --force-recreate
```

## Start

From the Duck application directory:

```bash
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:3200
```

Use the port configured in `.env` when it differs from `3200`.

## Stop

```bash
docker compose down
```

## Rebuild after source changes

```bash
docker compose up -d --build --force-recreate
```

## Verify the container identity

```bash
docker compose exec web id
```

With the standard local configuration, the result should include:

```text
uid=1000 gid=1000
```

## Project portability

Duck does not require projects to remain at fixed absolute paths.

* Move or rename a project within the configured projects directory without editing the project.
* Move the projects directory by changing the two global project paths in `.env`.
* Move the Duck application independently from the projects it manages.
* Keep project-local references relative to the project folder.

## Local configuration and generated files

The repository excludes local and generated material including:

* `.env`
* backups
* logs
* Python caches
* temporary patch scripts
* generated editor assets
* local dependency directories

`.env.dist` is tracked as the public configuration template.

## License

Duck is released under the GNU General Public License, version 3.

See [LICENSE](LICENSE).
