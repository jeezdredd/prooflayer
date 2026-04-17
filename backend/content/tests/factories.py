import io
import factory
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from content.models import Submission
from users.tests.factories import UserFactory


class SubmissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Submission

    user = factory.SubFactory(UserFactory)
    original_filename = factory.Sequence(lambda n: f"test_image_{n}.jpg")
    mime_type = "image/jpeg"
    file_size = 1024
    status = Submission.Status.PENDING

    @factory.lazy_attribute
    def file(self):
        img = Image.new("RGB", (100, 100), color="red")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        buffer.seek(0)
        return SimpleUploadedFile(self.original_filename, buffer.read(), content_type="image/jpeg")
