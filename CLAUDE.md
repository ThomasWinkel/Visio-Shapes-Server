# CLAUDE.md – Visio-Shapes-Server

## Projekt-Überblick

Web-Plattform zum weltweiten Teilen von Microsoft Visio Shapes und Stencils. Dieses Repository ist der **Server** – das Gegenstück ist ein **VSTO-AddIn** für Visio (separates Repository).

### Gesamtarchitektur

```
┌─────────────────────────────────────────────┐
│  Microsoft Visio                            │
│  ┌──────────────────────────────────────┐  │
│  │  VSTO-AddIn (C#)                     │  │
│  │  - Docking Panel mit WebView2        │  │
│  │  - Registriert Host-Object:          │  │
│  │    WebViewDragDrop.DragDropShape()   │  │
│  │  - Serialisiert Master-DataObjects   │  │
│  └──────────┬───────────────────────────┘  │
│             │ Microsoft.Web.WebView2        │
└─────────────┼───────────────────────────────┘
              │ HTTP
┌─────────────▼───────────────────────────────┐
│  Dieser Server (Flask)                      │
│  - Liefert die SPA aus                      │
│  - Speichert DataObjects + PNG-Vorschauen   │
│  - Stellt Shapes per API bereit             │
└─────────────────────────────────────────────┘
```

### Workflow: Shape hochladen
1. Nutzer selektiert Shape(s) oder eine ganze Schablone in Visio
2. AddIn serialisiert das Master-DataObject (Visio XML)
3. AddIn sendet PNG-Vorschau + DataObject per `POST /add_shape` oder `POST /add_stencil` (Token-Auth)
4. Server speichert beides in DB und Dateisystem

### Workflow: Shape herunterladen (Drag & Drop)
1. WebView2 zeigt diese SPA im Visio-Panel an
2. Nutzer drückt MouseDown auf eine Shape-Card
3. JS ruft `GET /get_shape/{id}` auf → Server gibt DataObject zurück
4. JS ruft `WebViewDragDrop.DragDropShape(dataObject)` auf
5. AddIn übernimmt DataObject, deserialisiert es
6. Nutzer droppt auf die Zeichenfläche → Shape wird platziert

### Hinweis zu `window.chrome.webview`
`window.chrome.webview.hostObjects.WebViewDragDrop` ist **kein Bug**, sondern das WebView2-Host-Object des AddIns. Funktioniert bewusst nur im Visio-WebView-Kontext, nicht im normalen Browser. Fehlendes Error-Handling ist aber ein Problem (JS-Fehler im Browser).

---

Auslieferung per Docker + Nginx Reverse Proxy.

---

## Tech Stack

| Bereich | Technologie |
|---|---|
| Backend | Flask 3, SQLAlchemy 2, Flask-Migrate (Alembic) |
| Auth | Flask-Login (Session) + Flask-HTTPAuth (Token) |
| Passwort | Flask-Bcrypt |
| Mail | Flask-Mail |
| Frontend | Vanilla JS, Web Components (Shadow DOM), SPA-Router |
| Package Manager | uv |
| Runtime | Gunicorn (4 Worker) |
| DB | SQLite (default) – jede SQLAlchemy-DB möglich |
| Config | python-decouple (.env) |

---

## Verzeichnisstruktur

```
/
├── app/                          # Flask-Package (root_path zeigt hierhin)
│   ├── __init__.py               # App-Factory: create_app()
│   ├── extensions.py             # db, migrate, bcrypt, login_manager, http_auth, mail, cors
│   ├── blueprints/
│   │   ├── auth/routes.py        # /login, /logout, /register, /token_login
│   │   └── visio/routes.py       # /get_shapes, /search, /get_shape, /download_stencil, /add_shape, /add_stencil
│   ├── models/
│   │   ├── auth.py               # User, Team, Role + Assoziationstabellen
│   │   └── visio.py              # Shape, Stencil, ShapeDownload, StencilDownload
│   ├── static/
│   │   ├── css/                  # style.css, fonts.css
│   │   ├── fonts/                # Open Sans WOFF2
│   │   ├── js/
│   │   │   ├── app.js            # Shape-Laden, Filter, Sort, Infinite Scroll
│   │   │   ├── router.js         # Client-seitiger SPA-Router
│   │   │   └── components/
│   │   │       └── shape-card.js # Web Component <shape-card>
│   │   └── images/shapes/        # Shape-Vorschau-PNGs ({id}.png)
│   ├── stencils/                 # Hochgeladene Stencil-Dateien ({id}{ext})
│   └── templates/                # Jinja2-Templates
├── migrations/                   # Alembic-Migrationen
├── instance/                     # Flask Instance-Folder → enthält app.db
├── config.py                     # Config-Klasse (liest .env via decouple)
├── Dockerfile
├── example_.env
├── example_docker-compose.yml
└── pyproject.toml
```

---

## Wichtige Pfade im Container

**WORKDIR im Dockerfile: `/usr/src/app`**

Weil WORKDIR und Flask-Package beide `app` heißen, ergibt sich ein doppeltes `app` in Container-Pfaden:

| Was | Pfad |
|---|---|
| `current_app.root_path` | `/usr/src/app/app/` |
| Static Files | `/usr/src/app/app/static/` |
| Shape-Bilder | `/usr/src/app/app/static/images/shapes/` |
| Stencil-Dateien | `/usr/src/app/app/stencils/` |
| Instance-Folder (DB) | `/usr/src/app/instance/` ← **kein** doppeltes app! |
| venv | `/usr/src/app/.venv/` |

Das `/app/app/` ist kein Bug, sondern Folge der Namenskonvention. Lösung wäre WORKDIR auf `/usr/src` zu ändern.

---

## Docker-Deployment

### Volume-Mounts (example_docker-compose.yml)

```yaml
- ./volumes/shapes:/usr/src/app/app/static/images/shapes
- ./volumes/stencils:/usr/src/app/app/stencils
- ./volumes/db:/usr/src/app/instance
```

### Deployment-Befehle

```bash
# Erstinstallation
mkdir -p volumes/shapes volumes/stencils volumes/db
chown -R 1000:1000 volumes/
git clone https://github.com/ThomasWinkel/Visio-Shapes-Server.git
cp Visio-Shapes-Server/example_.env .env
cp Visio-Shapes-Server/example_docker-compose.yml docker-compose.yml
docker-compose up -d --build
docker-compose exec www_visio /usr/src/app/.venv/bin/flask db upgrade

# Update
cd Visio-Shapes-Server && git pull && cd ..
docker-compose up -d --build
docker-compose exec www_visio /usr/src/app/.venv/bin/flask db upgrade
docker system prune -f
```

### Flask-Kommandos im Container

```bash
# Migrations ausführen (kein uv run – hat Home-Verzeichnis-Problem)
docker-compose exec www_visio /usr/src/app/.venv/bin/flask db upgrade
```

`uv run` **nicht** im Container verwenden – `appuser` hat kein Home-Verzeichnis, uv-Cache schlägt fehl.

---

## Authentifizierung

### Session-Auth (Flask-Login)
- Für: `/get_shape`, `/download_stencil`
- Login via `/login` (E-Mail + Passwort) oder `/token_login` (Token)
- `remember=True` → persistentes Cookie

### Token-Auth (Flask-HTTPAuth)
- Für: `/add_shape`, `/add_stencil`
- Header: `Authorization: Bearer <token>`
- Token im `User.token`-Feld gespeichert
- Token = `"#" + generiertes_passwort` (wird bei Registrierung erzeugt)

### Registrierungsflow
1. E-Mail + Name eingeben
2. 10-stelliges Passwort wird generiert
3. E-Mail mit Passwort wird verschickt
4. Nutzer wird nach 5 Minuten automatisch gelöscht, wenn kein Login erfolgt (Background-Timer)

---

## Datenmodell

```
User ──< Shape
User ──< Stencil
Stencil ──< Shape (cascade delete)
Shape ──< ShapeDownload
Stencil ──< StencilDownload
User >──< Team (m:n)
User >──< Role (m:n)
```

**Hinweis:** `Team` und `Role` sind im Datenmodell vollständig definiert, werden im Code aber **nirgends genutzt** (tote Strukturen, vermutlich für spätere Erweiterung).

---

## Bekannte Bugs & Probleme

### Frontend-Bugs (kritisch)
- **`shape.rating` existiert nicht** (`app.js`): Sortierung nach Rating greift auf ein Feld zu, das weder im Modell noch in `serialize()` vorhanden ist. Sortierung funktioniert nicht.
- **`categories` ist String, kein Array** (`app.js`): `shape.categories.includes(selectedCategory)` sucht als Substring, nicht als exaktes Kategorie-Match. Kann falsche Treffer liefern.
- **WebView ohne Error-Handling**: `WebViewDragDrop.DragDropShape()` ist bewusst nur im Visio-WebView verfügbar, aber es fehlt ein `try/catch` → unkontrollierter JS-Fehler wenn die Seite im normalen Browser geöffnet wird.

### Backend-Bugs
- **Race Condition bei Shape-ID** (`/add_stencil`): Shape-IDs werden manuell mit `max(id)+1` berechnet – bei gleichzeitigen Uploads können doppelte IDs entstehen. Sollte auf DB-seitiges Auto-Increment vertrauen.
- **Keine Transaktion in `/add_stencil`**: DB-Commit passiert vor dem Dateispeichern. Wenn Dateispeicherung fehlschlägt, entstehen inkonsistente Daten.
- **Timer-Deletion nicht persistent**: Der 5-Minuten-Lösch-Timer überlebt keinen Server-Neustart.

### Fehlende Features
- Kein Löschen von Shapes/Stencils (kein DELETE-Endpoint)
- Kein Bearbeiten von Metadaten
- Kein Passwort-Reset
- Keine Datei-Validierung bei Uploads (Typ, Größe)
- Kein Rate-Limiting auf `/register`
- `/get_shapes` lädt **alle** Shapes auf einmal – skaliert nicht

---

## Entwicklung lokal

```bash
uv sync
uv run flask run        # Dev-Server
uv run flask db migrate -m "beschreibung"
uv run flask db upgrade
```

---

## Kontext zur Entwicklung

Der Autor ist kein professioneller Entwickler und hat keine Webentwicklungserfahrung. Das Projekt ist ein funktionierender Proof-of-Concept. Claude unterstützt bei der Weiterentwicklung – alle Änderungen bitte verständlich erklären, Entscheidungen begründen, nichts stillschweigend voraussetzen.

---

## Was ich ändern würde (Priorität)

1. **`app.js` – `shape.rating` fix**: Feld aus `serialize()` entfernen oder Datenmodell ergänzen
2. **`app.js` – categories**: String-Matching korrigieren (`split(',').map(s => s.trim())`)
3. **WebView-Calls absichern**: `try/catch` um alle `chrome.webview`-Aufrufe
4. **`/add_stencil` – Transaktion**: Dateien vor DB-Commit speichern oder Rollback bei Fehler
5. **WORKDIR auf `/usr/src`** ändern: Beseitigt `app/app/`-Dopplung ohne Codeänderungen
6. **Pagination in `/get_shapes`**: Für Skalierbarkeit
7. **Dateivalidierung**: Typ + Größe bei Uploads prüfen
