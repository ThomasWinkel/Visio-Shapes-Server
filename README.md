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

### Local Testing

**1. Clone and enter the repo**
```bash
git clone https://github.com/ThomasWinkel/Visio-Shapes-Server.git
cd Visio-Shapes-Server
```

**2. Create `.env`**
```bash
cp example_.env .env
```
Edit `.env` – fill in your mail credentials and set `OWNER_EMAIL`.

**3. Install dependencies**
```bash
uv sync
```

**4. Init the database**
```bash
uv run flask db upgrade
```

**5. Run the development server**
```bash
uv run flask run
```
The server will be available on:  
http://localhost:5000/

---

### Production (Docker)

#### Prerequisites

- Git
- Docker and Docker Compose
- A reverse proxy (e.g. nginx) handling HTTPS and forwarding to port 5000

#### Steps

**1. Create required directories**
```bash
mkdir -p /services/visio-shapes-server
cd /services/visio-shapes-server
mkdir -p volumes/shapes volumes/stencils volumes/db
chown -R 1000:1000 volumes/
```

**2. Clone the repository**
```bash
git clone https://github.com/ThomasWinkel/Visio-Shapes-Server.git
```

**3. Configure environment**
```bash
cp Visio-Shapes-Server/example_.env .env
```

Edit `.env` and set all values, especially `SECRET_KEY`, and the `MAIL_*` settings. See [Configuration](#configuration) for details.

**4. Configure docker-compose**
```bash
cp Visio-Shapes-Server/example_docker-compose.yml docker-compose.yml
```

Edit `docker-compose.yml` and adapt to your setup.

**5. Build and start the container**
```bash
docker-compose up -d --build
```

**6. Run database migrations**
```bash
docker-compose exec www_visio /usr/src/app/.venv/bin/flask db upgrade
```

The application is now available on port `5000`.

**7. Set up the daily status mail (optional)**

Add a cron job on the host to send a daily status e-mail to `OWNER_EMAIL`:
```bash
crontab -e
```
```cron
# Daily at 07:00 UTC
0 7 * * * cd /services/visio-shapes-server && docker compose exec -T www_visio /usr/src/app/.venv/bin/flask send_status_mail >> /var/log/visio_status_mail.log 2>&1
```

**8. Maintenance**

To update the application to the latest version:
```bash
cd /services/visio-shapes-server/Visio-Shapes-Server
git pull
cd ..
docker-compose up -d --build
docker-compose exec www_visio /usr/src/app/.venv/bin/flask db upgrade
docker system prune -f
```

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
