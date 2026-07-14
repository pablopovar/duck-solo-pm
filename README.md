
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

The project folder remains portable. Duck discovers it through `.pocket/config.md`; no application-specific database entry is required.

## Application structure

```text
duck-solo-pm/
├── app/
├── docs/
├── web/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Requirements

* Docker
* Docker Compose
* A directory containing the projects Duck should manage

The desktop **Open folder** and **Open terminal** controls require the local Duck desktop launcher to be installed on the computer running the browser.

## Configuration

Create a `.env` file in the application directory:

```dotenv
POCKET_PROJECTS_PATH=/path/to/projects
POCKET_PROJECTS_HOST_PATH=/path/to/projects
POCKET_PORT=3200
```

Replace `/path/to/projects` with the directory containing your project folders.

The application directory and projects directory may be moved independently. Update `.env` when the projects root changes; individual projects do not need to be reconfigured.

## Start

From the Duck application directory:

```bash
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:3200
```

## Stop

```bash
docker compose down
```

## Rebuild after source changes

```bash
docker compose up -d --build
```

## Project portability

Duck does not require projects to remain at fixed absolute paths.

* Move or rename a project within the configured projects directory without editing that project.
* Move the projects directory by changing the global path in `.env`.
* Move the Duck application independently from the projects it manages.
* Project-local references should use paths relative to the project folder.

## License

Duck is released under the GNU General Public License, version 3.

See [LICENSE](LICENSE).
