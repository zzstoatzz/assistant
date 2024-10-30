from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

try:
    import google.auth.external_account_authorized_user
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

    def __post_init__(self) -> None:
        self.content = {
            'subject': self.subject,
            'sender': self.sender,
            'snippet': self.snippet,
            'thread_id': self.thread_id,
            'labels': self.labels,
        }
        super().__post_init__()


def get_gmail_service(creds_path: Path, token_path: Path) -> Resource:
    """Initialize and return the Gmail service"""
    creds: Credentials | google.auth.external_account_authorized_user.Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, GmailObserver.SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, GmailObserver.SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


class GmailObserver(BaseModel, Observer[dict[str, Any], EmailEvent]):
    """Gmail implementation of the Observer protocol"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    SCOPES: ClassVar[list[str]] = ['https://www.googleapis.com/auth/gmail.modify']

    creds_path: Path
    token_path: Path
    service: Resource | None = None

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
        self.service = get_gmail_service(self.creds_path, self.token_path)

    def observe(self) -> Iterator[EmailEvent]:
        """Stream unread emails as events"""
        if not self.service:
            raise RuntimeError('Observer not connected')

        results = (
            self.service.users()  # type: ignore
            .messages()
            .list(
                userId='me',
                labelIds=['UNREAD'],
            )
            .execute()
        )

        if not (messages := results.get('messages')):
            return iter([])

        for msg in messages:
            message = self.service.users().messages().get(userId='me', id=msg['id']).execute()  # type: ignore

            # Only process if message is actually unread
            if 'UNREAD' not in message['labelIds']:
                continue

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
            self.service.users().messages().modify(  # type: ignore
                userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}
            ).execute()

    def disconnect(self) -> None:
        self.service = None
