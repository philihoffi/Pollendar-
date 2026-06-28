# Pollendar - Discord Calendar Bot

[![Lint](https://github.com/philihoffi/Pollendar-/actions/workflows/lint.yml/badge.svg)](https://github.com/philihoffi/Pollendar-/actions/workflows/lint.yml)
[![Test](https://github.com/philihoffi/Pollendar-/actions/workflows/test.yml/badge.svg)](https://github.com/philihoffi/Pollendar-/actions/workflows/test.yml)
[![Docker](https://github.com/philihoffi/Pollendar-/actions/workflows/docker.yml/badge.svg)](https://github.com/philihoffi/Pollendar-/actions/workflows/docker.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Pollendar is a Discord bot designed for calendar management using Slash Commands. It synchronizes events with the Google Calendar API, ensuring your schedule is accessible across various platforms like Apple Calendar (via CalDAV), Google Calendar clients, and other integrated services.

## 🚀 Features

- **Slash Commands**: Intuitive commands for adding, listing, editing, and deleting events.
- **Google Calendar Sync**: Real-time synchronization with Google Calendar.
- **Short-ID System**: Uses 8-character IDs for easy event identification within Discord.
- **Access Control**: Optional whitelist to restrict bot usage to specific users.
- **Dockerized**: Easy deployment using Docker and Docker Compose.
- **Localized**: Default support for German date/time formats and Berlin timezone.

## 🏗️ Architecture

```text
Discord (Slash Commands) → Python Bot (Docker) → Google Calendar API → Other Clients (CalDAV Sync)
```

The bot only establishes outgoing HTTPS connections. No incoming ports or web servers are required.

## 📁 Project Structure

```text
.
├── src/                          # Source code
│   ├── __main__.py               # Entry point (python -m src)
│   ├── bot.py                    # Bot initialization and configuration
│   ├── calendar_client.py        # Google Calendar API wrapper
│   ├── cogs/
│   │   └── event_commands.py     # Discord slash commands (/event)
│   └── utils/
│       └── helpers.py            # Validation, access control, and formatting
├── tests/                        # Unit tests (pytest)
│   └── test_helpers.py
├── .github/
│   ├── workflows/                # GitHub Actions CI/CD
│   │   ├── lint.yml              # Ruff linting
│   │   ├── test.yml              # Pytest
│   │   └── docker.yml            # Build & push to GHCR
│   ├── ISSUE_TEMPLATE/           # Bug report & feature request templates
│   └── PULL_REQUEST_TEMPLATE.md  # PR template
├── .env.example                  # Environment variables template
├── docker-compose.yml            # Docker deployment configuration
├── Dockerfile                    # Container build instructions
├── pyproject.toml                # Project config (ruff, pytest)
├── requirements.txt              # Python dependencies
└── test_calendar_connection.py   # Connection test script
```

## 🛠️ Prerequisites

- **Docker & Docker Compose** (running on a Raspberry Pi, NAS, or Server).
- **Discord Developer Portal**: An application with a Bot token.
- **Google Cloud Platform**: A project with the **Google Calendar API** enabled and a **Service Account**.

## ⚙️ Setup Instructions

### 1. Discord Bot Configuration

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a **New Application**.
2. Navigate to **Bot** → **Add Bot**.
3. Copy the **Token**.
4. Disable the **Public Bot** option (so only you can invite it).
5. Go to **OAuth2** → **URL Generator**:
   - Select Scopes: `bot` + `applications.commands`.
   - Select Permissions: `Send Messages` + `Use Slash Commands`.
6. Open the generated URL in your browser to invite the bot to your server.

### 2. Google Cloud Setup

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create a new project.
2. Navigate to **APIs & Services** → **Library** and enable the **Google Calendar API**.
3. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **Service Account**.
4. Provide a name and click **Create and Continue**.
5. After creation, click on the service account, go to **Keys** → **Add Key** → **Create New Key** → **JSON**.
6. Download the JSON file; you will need this for the deployment.

### 3. Calendar Permissions

1. Open [Google Calendar](https://calendar.google.com/).
2. Find (or create) the calendar you want the bot to manage.
3. Go to **Settings and sharing** → **Share with specific people or groups**.
4. Add the **Service Account Email** (found in your JSON file, e.g., `name@project.iam.gserviceaccount.com`).
5. Set permissions to **Make changes to events**.
6. Under **Integrate calendar**, copy the **Calendar ID**.

## 🚢 Deployment

### 4. Prepare Service Account Key

Place the `service_account.json` at a permanent location on your host system, for example:
```bash
/volume1/docker/pollendar/service_account.json
```

### 5. Docker Compose Configuration

Use the following environment variables in your `docker-compose.yml` or `.env` file:

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Your Discord Bot Token |
| `CALENDAR_ID` | Your Google Calendar ID |
| `CREDENTIALS_SOURCE` | Path to `service_account.json` on the **Host** system |
| `ALLOWED_USER_IDS` | Comma-separated Discord User IDs (optional, empty = all allowed) |

### 6. Portainer Stack (Optional)

1. Create a new Stack in Portainer.
2. Point it to this repository: `https://github.com/philihoffi/Pollendar-`.
3. Fill in the **Environment variables** as listed above.
4. **Deploy the stack**.

## ⌨️ Command Reference

| Command | Parameters | Description |
|---|---|---|
| `/hallo` | - | Test command - Bot responds with a greeting |
| `/event add` | `title`, `date`, `start`, `end` (opt.) | Create a new event via modal |
| `/event list` | `range: today / week / month` | List upcoming events |
| `/event edit` | `event_id`, various fields (opt.) | Edit an existing event via modal |
| `/event del` | `event_id` | Delete an event (requires confirmation) |

### Formats & Identification

- **Date**: `DD.MM.YYYY` (e.g., `24.12.2024`)
- **Time**: `HH:MM` (e.g., `14:30`)
- **Timezone**: Default is `Europe/Berlin`.
- **Short-ID**: Every event is identified by an 8-character Short-ID (the first 8 characters of its Google ID). Use this ID for `/event edit` and `/event del`.

> [!NOTE]
> To optimize performance, the bot searches for Short-IDs within a window of **7 days in the past** to **60 days in the future**. Events outside this range might not be found via Short-ID.

## 🔒 Security

If `ALLOWED_USER_IDS` is set, only specified users can interact with the bot. If left empty, anyone on the server can use the commands.

## 📄 License

This project is licensed under the MIT License.