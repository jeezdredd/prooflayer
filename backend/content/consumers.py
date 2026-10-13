import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from classroom.access import can_view_submission

logger = logging.getLogger(__name__)


@database_sync_to_async
def _may_watch(user, sub_id: str) -> bool:
    try:
        return can_view_submission(user, sub_id)
    except Exception:
        return False


class SubmissionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        sub_id = self.scope["url_route"]["kwargs"]["sub_id"]

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        if not await _may_watch(user, sub_id):
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
