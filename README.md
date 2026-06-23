# Discord Calendar Bot

Ein Discord-Bot zur Kalenderverwaltung per Slash-Commands. Events werden via Google Calendar API synchronisiert und sind in Apple Kalender (CalDAV) sowie anderen Google-Kalender-Clients sichtbar.

## Architektur

```
Discord (Slash Commands) → Python Bot (Docker) → Google Calendar API → Apple Kalender (CalDAV-Sync)
```

Der Bot stellt nur ausgehende HTTPS-Verbindungen her. Es wird kein eingehender Port oder Webserver benötigt.

## Projektstruktur

```
.
├── src/                          # Quellcode (Python-Paket)
│   ├── __main__.py               # Einstiegspunkt (python -m src)
│   ├── bot.py                    # Bot-Initialisierung, Config, main()
│   ├── calendar_client.py        # Google Calendar API Wrapper
│   ├── cogs/
│   │   └── event_commands.py     # /event add/list/edit/del
│   └── utils/
│       └── helpers.py            # Zugriffsschutz, Datum/Zeit
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── test_calendar_connection.py
```

## Voraussetzungen

- Docker + Docker Compose (auf dem Raspberry Pi / NAS)
- Discord Developer Portal – eine Application mit Bot
- Google Cloud Platform – ein Projekt mit aktivierter Calendar API und Service Account

## Setup

### 1. Discord Developer Portal

1. Gehe zu https://discord.com/developers/applications und erstelle eine **New Application**.
2. Gehe zu **Bot** → **Add Bot**.
3. Kopiere den **Token** unter dem Bot-Namen.
4. Deaktiviere unter **Bot** die Option **Public Bot** (nur du kannst den Bot einladen).
5. Gehe zu **OAuth2** → **URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Berechtigungen: `Send Messages` + `Use Slash Commands`
6. Öffne die generierte URL in einem Browser, um den Bot auf deinen Server einzuladen.

### 2. Google Cloud Setup

1. Gehe zu https://console.cloud.google.com/ und erstelle ein neues Projekt.
2. Navigiere zu **APIs & Dienste** → **Bibliothek** und aktiviere die **Google Calendar API**.
3. Gehe zu **APIs & Dienste** → **Anmeldedaten** → **Anmeldedaten erstellen** → **Dienstkonto**.
4. Gib einen Namen ein und klicke auf **Erstellen und fortfahren**.
5. Nach der Erstellung klicke auf das Dienstkonto, gehe zu **Schlüssel** → **Schlüssel hinzufügen** → **Neuen Schlüssel erstellen** → **JSON**.
6. Lade die JSON-Datei herunter – diese wird gleich in Portainer als Config benötigt.

### 3. Google Kalender freigeben

1. Öffne https://calendar.google.com/.
2. Finde (oder erstelle) den Kalender, den der Bot verwenden soll.
3. Gehe zu Kalendereinstellungen → **Für bestimmte Personen freigeben**.
4. Füge die **E-Mail-Adresse des Service Account** (aus der JSON-Datei, z. B. `name@project.iam.gserviceaccount.com`) hinzu.
5. Wähle die Berechtigung **Ereignisse bearbeiten**.
6. Kopiere die Kalender-ID aus den Kalendereinstellungen unter **Kalender-ID**.

## Portainer Deployment

### 4. Service-Account-JSON aufs NAS legen

Lege die `service_account.json` an einem festen Pfad auf deinem NAS ab, z. B.:
```
/volume1/docker/pollendar/service_account.json
```

### 5. Stack anlegen

1. Portainer → **Stacks** → **Add stack**
2. Name: `pollendar`
3. **Build method**: Repository
4. Repository URL: `https://github.com/philihoffi/Pollendar-`
5. **Compose path**: `docker-compose.yml`
6. **Environment variables** (ausfüllen):

| Variable | Wert |
|---|---|
| `DISCORD_TOKEN` | Dein Discord Bot-Token |
| `CALENDAR_ID` | Deine Google Calendar-ID |
| `CREDENTIALS_SOURCE` | Pfad zur `service_account.json` auf dem NAS, z. B. `/volume1/docker/pollendar/service_account.json` |
| `ALLOWED_USER_IDS` | Discord-IDs (optional, leer = alle erlaubt) |

7. **Deploy the stack**

### 6. Auto-Update (Webhook)

1. Portainer → Stack `pollendar` → **Webhook** → kopiere die Webhook-URL
2. GitHub → Repo → Settings → Webhooks → **Add webhook**
3. Payload URL: Portainer-Webhook-URL einfügen
4. Events: `Just the push event`
5. **Add webhook**

## Command-Referenz

| Command | Parameter | Beschreibung |
|---|---|---|
| `/hallo` | – | Test – Bot antwortet |
| `/event add` | `titel`, `datum` (TT.MM.JJJJ), `startzeit` (HH:MM), `endzeit` (opt.) | Neues Event anlegen |
| `/event list` | `bereich: heute / woche / monat` | Events auflisten |
| `/event edit` | `event_id`, `titel`/`datum`/`startzeit`/`endzeit` (opt.) | Event bearbeiten |
| `/event del` | `event_id` | Event löschen |

### Datums- und Zeitformat

- Datum: `TT.MM.JJJJ` (z. B. `24.12.2024`)
- Zeit: `HH:MM` (z. B. `14:30`)
- **Zeitzone**: `Europe/Berlin` (UTC+1 / UTC+2)

### Kurz-ID

Jedes Event erhält beim Anlegen eine 8-stellige Kurz-ID (erste 8 Zeichen der Google-Event-ID). Diese wird in `/event edit` und `/event del` verwendet.

## Zugriffsschutz

Ist `ALLOWED_USER_IDS` gesetzt, dürfen nur diese User den Bot verwenden. Ist die Liste leer, ist der Bot für alle auf dem Server geöffnet.

## Lizenz

MIT