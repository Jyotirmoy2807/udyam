from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models import Notification
from app.events import emit
from app.ports import NotifierPort


class OutboxNotifier:
    """Outbox notification adapter implementing NotifierPort."""

    def __init__(self, session: Session):
        self.session = session

    def send(self, lead_id: UUID, channel: str, template: str, body: str) -> None:
        notif = Notification(
            lead_id=lead_id,
            channel=channel,
            template=template,
            body=body,
            sent_at=datetime.now(timezone.utc),
        )
        self.session.add(notif)
        self.session.flush()

        emit(
            session=self.session,
            type="NOTIFICATION_SENT",
            lead_id=lead_id,
            payload={
                "notification_id": str(notif.id),
                "channel": channel,
                "template": template,
            },
        )
        self.session.commit()
