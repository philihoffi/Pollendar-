import logging
from datetime import date, datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils.helpers import TZ

logger = logging.getLogger(__name__)

SEARCH_DAYS_BEFORE = 7
SEARCH_DAYS_AFTER = 60


class GoogleCalendarClient:
    def __init__(self, calendar_id: str, credentials_path: str):
        self.calendar_id = calendar_id
        creds = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        self.service = build('calendar', 'v3', credentials=creds)
        self._short_id_cache: dict[str, str] = {}

    def _to_rfc3339(self, dt: datetime) -> str:
        return dt.astimezone(TZ).isoformat()

    def _short_id(self, event_id: str) -> str:
        return event_id[:8]

    def _search_by_short_id(self, short_id: str) -> str | None:
        if short_id in self._short_id_cache:
            return self._short_id_cache[short_id]

        now = datetime.now(TZ)
        time_min = now - timedelta(days=SEARCH_DAYS_BEFORE)
        time_max = now + timedelta(days=SEARCH_DAYS_AFTER)

        try:
            page_token = None
            while True:
                events_result = self.service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy='startTime',
                    pageToken=page_token,
                ).execute()

                for event in events_result.get('items', []):
                    full_id = event['id']
                    if full_id.startswith(short_id):
                        self._short_id_cache[short_id] = full_id
                        return full_id

                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break

            logger.warning(f"Event with short ID {short_id} not found in search window.")
            return None
        except HttpError as e:
            logger.error(f"Failed to search events by short ID: {e}")
            raise

    def add_event(self, title: str, start_dt: datetime, end_dt: datetime | None = None) -> str:
        if end_dt is None:
            end_dt = start_dt + timedelta(hours=1)

        event = {
            'summary': title,
            'start': {
                'dateTime': self._to_rfc3339(start_dt),
                'timeZone': 'Europe/Berlin',
            },
            'end': {
                'dateTime': self._to_rfc3339(end_dt),
                'timeZone': 'Europe/Berlin',
            },
        }

        try:
            created = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            full_id = created['id']
            sid = self._short_id(full_id)
            self._short_id_cache[sid] = full_id
            logger.info(f"Event created: {title} (ID: {sid})")
            return full_id
        except HttpError as e:
            logger.error(f"Failed to create event: {e}")
            raise

    def get_event(self, full_id: str) -> dict:
        try:
            return self.service.events().get(
                calendarId=self.calendar_id,
                eventId=full_id
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to get event {full_id}: {e}")
            raise

    def list_events(self, start_date: date, end_date: date) -> list[dict]:
        time_min = TZ.localize(datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0))
        time_max = TZ.localize(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59))

        try:
            page_token = None
            all_events = []
            while True:
                events_result = self.service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy='startTime',
                    pageToken=page_token,
                ).execute()

                all_events.extend(events_result.get('items', []))

                page_token = events_result.get('nextPageToken')
                if not page_token:
                    break

            result = []
            for event in all_events:
                full_id = event['id']
                sid = self._short_id(full_id)
                self._short_id_cache[sid] = full_id

                start_raw = event['start'].get('dateTime', event['start'].get('date'))
                result.append({
                    'id': sid,
                    'full_id': full_id,
                    'title': event.get('summary', '(kein Titel)'),
                    'start': start_raw,
                })

            return result
        except HttpError as e:
            logger.error(f"Failed to list events: {e}")
            raise

    def update_event(self, short_id: str, title: str | None = None,
                     start_dt: datetime | None = None,
                     end_dt: datetime | None = None) -> dict:
        full_id = self._search_by_short_id(short_id)
        if not full_id:
            raise ValueError(f"Event mit ID {short_id} nicht gefunden.")

        body = {}
        if title is not None:
            body['summary'] = title
        if start_dt is not None:
            body['start'] = {
                'dateTime': self._to_rfc3339(start_dt),
                'timeZone': 'Europe/Berlin',
            }
        if end_dt is not None:
            body['end'] = {
                'dateTime': self._to_rfc3339(end_dt),
                'timeZone': 'Europe/Berlin',
            }

        try:
            updated = self.service.events().patch(
                calendarId=self.calendar_id,
                eventId=full_id,
                body=body
            ).execute()
            logger.info(f"Event updated: {short_id}")
            return updated
        except HttpError as e:
            logger.error(f"Failed to update event {short_id}: {e}")
            raise

    def delete_event(self, short_id: str) -> str:
        full_id = self._search_by_short_id(short_id)
        if not full_id:
            raise ValueError(f"Event mit ID {short_id} nicht gefunden.")

        try:
            event = self.get_event(full_id)
            title = event.get('summary', '(kein Titel)')
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=full_id
            ).execute()
            logger.info(f"Event deleted: {title} (ID: {short_id})")
            return title
        except HttpError as e:
            logger.error(f"Failed to delete event {short_id}: {e}")
            raise
