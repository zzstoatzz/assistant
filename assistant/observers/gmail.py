from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import Resource, build
except ImportError:
    raise RuntimeError('Missing gmail dependencies, run `pip install "assistant[gmail]"`')

from assistant.observer import BaseEvent, Observer


@dataclass
class EmailEvent(BaseEvent):
    """Email event data"""

    subject: str = field(default='No Subject')
    sender: str = field(default='Unknown Sender')
    snippet: str = field(default='')
    thread_id: str = field(default='')
    labels: list[str] = field(default_factory=list)


class GmailObserver(BaseModel, Observer[dict[str, Any], EmailEvent]):
    """Gmail implementation of the Observer protocol"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    SCOPES: ClassVar[list[str]] = ['https://www.googleapis.com/auth/gmail.modify']

    creds_path: Path
    token_path: Path
    service: Resource | None = None

    def _get_gmail_service(self) -> Resource:
        """Initialize and return the Gmail service"""
        creds: Credentials | None = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            self.token_path.write_text(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def _get_email_details(self, message: dict[str, Any]) -> tuple[str, str]:
        """Extract subject and sender from message headers"""
        headers = message['payload']['headers']
        subject = next(
            (header['value'] for header in headers if header['name'].lower() == 'subject'),
            'No Subject',
        )
        sender = next(
            (header['value'] for header in headers if header['name'].lower() == 'from'),
            'Unknown Sender',
        )
        return subject, sender

    def connect(self) -> None:
        self.service = self._get_gmail_service()

    def observe(self) -> Iterator[EmailEvent]:
        """Stream unread emails as events"""
        if not self.service:
            raise RuntimeError('Observer not connected')

        results = (
            self.service.users()
            .messages()
            .list(
                userId='me',
                labelIds=['UNREAD'],
            )
            .execute()
        )

        if not (messages := results.get('messages')):
            return

        for msg in messages:
            message = self.service.users().messages().get(userId='me', id=msg['id']).execute()

            subject, sender = self._get_email_details(message)
            yield EmailEvent(
                id=message['id'],
                source_type='email',
                subject=subject,
                sender=sender,
                snippet=message['snippet'],
                thread_id=message['threadId'],
                labels=message['labelIds'],
                raw_source=message['id'],
            )

            # Mark as read after processing
            self.service.users().messages().modify(
                userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}
            ).execute()

    def disconnect(self) -> None:
        self.service = None
