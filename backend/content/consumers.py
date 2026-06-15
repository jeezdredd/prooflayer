import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger(__name__)


@database_sync_to_async
def _get_submission_owner_id(sub_id: str) -> int | None:
    from content.models import Submission
    try:
        return Submission.objects.values_list("user_id", flat=True).get(id=sub_id)
    except (Submission.DoesNotExist, Exception):
        return None


class SubmissionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        sub_id = self.scope["url_route"]["kwargs"]["sub_id"]

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        owner_id = await _get_submission_owner_id(sub_id)
        if owner_id is None or (owner_id != user.id and not user.is_staff):
            await self.close(code=4003)
            return

        self.group_name = f"submission_{sub_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def submission_update(self, event):
        await self.send_json(event["payload"])
