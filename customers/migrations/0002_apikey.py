from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApiKey',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key_prefix', models.CharField(db_index=True, max_length=8)),
                ('key_hash', models.CharField(max_length=64, unique=True)),
                ('label', models.CharField(blank=True, max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='api_keys', to='customers.customer')),
            ],
            options={'indexes': [models.Index(fields=['key_prefix', 'is_active'], name='customers_a_key_pre_idx')]},
        ),
    ]
