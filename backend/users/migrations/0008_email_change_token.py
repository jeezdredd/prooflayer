import django.db.models.deletion
import users.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_email_language_updates'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailChangeToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('new_email', models.EmailField(max_length=254)),
                ('token', models.CharField(db_index=True, default=users.models._gen_token, max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(default=users.models.email_change_expiry)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_change_tokens', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'email_change_tokens',
                'ordering': ['-created_at'],
                'constraints': [models.UniqueConstraint(condition=models.Q(('cancelled_at__isnull', True), ('used_at__isnull', True)), fields=('user',), name='one_open_email_change_per_user')],
            },
        ),
    ]
