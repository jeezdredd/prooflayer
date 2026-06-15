import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tier", models.CharField(choices=[("free", "Free"), ("pro", "Pro"), ("education", "Education"), ("enterprise", "Enterprise")], default="free", max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("past_due", "Past Due"), ("cancelled", "Cancelled"), ("trialing", "Trialing")], default="active", max_length=20)),
                ("stripe_customer_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("stripe_subscription_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "subscriptions"},
        ),
    ]
