from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="subscription",
            old_name="stripe_customer_id",
            new_name="paddle_customer_id",
        ),
        migrations.RenameField(
            model_name="subscription",
            old_name="stripe_subscription_id",
            new_name="paddle_subscription_id",
        ),
    ]
