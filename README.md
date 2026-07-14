# Door to Pocket — Version 0

A read-only dashboard for seeing project folders and Markdown pages.

## Current filesystem layout

Application:

```text
/home/pablo/ownCloud/Projects/ai-systems-observer/LocalStack/pocket/
```

Project data:

```text
/home/pablo/ownCloud/Projects/ai-systems-observer/ai-observer/projects/
```

No host path is hardcoded into the application or image. By default, Compose reaches the current data folder through this relative path:

```text
../../ai-observer/projects
```

If either directory moves independently, set `POCKET_PROJECTS_PATH` in `.env`.

## Install in the intended application directory

Copy this package into:

```text
/home/pablo/ownCloud/Projects/ai-systems-observer/LocalStack/pocket/
```

The directory should then contain:

```text
pocket/
├── app/
├── compose.yaml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Start

```bash
cd /home/pablo/ownCloud/Projects/ai-systems-observer/LocalStack/pocket
docker compose up -d --build
```

Open:

```text
http://127.0.0.1:4177
```

## Stop

```bash
docker compose down
```

## Relocate the project data

Create `.env` beside `compose.yaml`:

```bash
cp .env.example .env
```

Then edit only this value:

```dotenv
POCKET_PROJECTS_PATH=/new/location/projects
```

The value may be absolute or relative to the directory containing `compose.yaml`.

## Relocate the Pocket application

Move the entire application directory. If the relative relationship to the data folder changes, update `POCKET_PROJECTS_PATH` in `.env`. No Python, HTML, Dockerfile, or Compose source needs editing.

## Included in this version

- One Door to Pocket container.
- Read-only bind mount of the projects data directory.
- Immediate project folders shown in the left panel.
- Folder navigation inside a project.
- Markdown pages rendered for reading.
- Hidden files and folders omitted.
- Loose files at the projects-root level ignored.

## Not included

- Search.
- User-facing sorting.
- Editing.
- Folder or page creation.
- Project management operations.
- Authentication or multi-user permissions.
- Firefox capture.
- Chat.
- Stream processing.
- Database.
- Docker socket access.
- Docker-in-Docker.
