# Visio-Shapes-Server

A web platform for sharing and discovering Microsoft Visio shapes and stencils. Users can browse and download shapes, and contribute their own stencils via a token-authenticated API.

## Tech Stack

- **Backend:** Flask 3, SQLAlchemy 2, Flask-Migrate (Alembic)
- **Auth:** Flask-Login (session) + Flask-HTTPAuth (token)
- **Frontend:** Vanilla JS SPA with custom Web Components
- **Package manager:** uv
- **Runtime:** Gunicorn
- **Database:** SQLite (default) / any SQLAlchemy-supported database

## Features

- Browse and search Visio shapes with infinite scroll
- Download shapes and stencils (registered users only)
- Upload shapes and stencils via REST API (token auth)
- Email-based registration with auto-generated passwords
- Download tracking per user

## Installation

### Prerequisites

- Git
- Docker and Docker Compose
- A reverse proxy (e.g. nginx) handling HTTPS and forwarding to port 5000

### Steps

**1. Clone the repository**
```bash
git clone <repository-url>
cd <repository-folder>
```

**2. Configure environment**
```bash
cp env_example .env
```

Edit `.env` and set all values, especially `SECRET_KEY`, `DATABASE_URI`, and the `MAIL_*` settings. See [Configuration](#configuration) for details.

**3. Create required directories**
```bash
mkdir -p app/stencils app/static/images/shapes
```

**4. Build and start the container**
```bash
docker compose up -d --build
```

**5. Run database migrations**
```bash
docker compose exec app uv run flask db upgrade
```

The application is now available on port `5000`.

> On subsequent deployments, repeat steps 4 and 5.

## Configuration

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Flask session secret — use a long random string | `openssl rand -hex 32` |
| `DATABASE_URI` | SQLAlchemy connection string | `sqlite:///app.db` |
| `MAIL_SERVER` | SMTP server hostname | `smtp.example.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USE_TLS` | Enable STARTTLS | `True` |
| `MAIL_USE_SSL` | Enable SMTPS | `False` |
| `MAIL_USERNAME` | SMTP login | `mail@example.com` |
| `MAIL_PASSWORD` | SMTP password | |
| `MAIL_DEFAULT_SENDER` | Sender name and address | `"My Name <mail@example.com>"` |

## Development

```bash
# Install dependencies
uv sync

# Run development server
uv run flask run

# Database migrations
uv run flask db migrate -m "description"
uv run flask db upgrade
```

## API

Write endpoints require HTTP token authentication (`Authorization: Bearer <token>`).

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/get_shapes` | — | List all shapes |
| `GET/POST` | `/search` | — | Search shapes by name |
| `GET` | `/get_shape/<id>` | Session | Get shape data object |
| `GET` | `/download_stencil/<id>` | Session | Download stencil file |
| `POST` | `/add_shape` | Token | Upload a single shape |
| `POST` | `/add_stencil` | Token | Upload a stencil with shapes |
