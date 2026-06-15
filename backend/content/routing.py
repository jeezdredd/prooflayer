from django.urls import re_path

from content.consumers import SubmissionConsumer

websocket_urlpatterns = [
    re_path(r"ws/submissions/(?P<sub_id>[0-9a-f-]+)/$", SubmissionConsumer.as_asgi()),
]
