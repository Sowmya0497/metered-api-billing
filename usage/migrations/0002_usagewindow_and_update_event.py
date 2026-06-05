from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
        ('usage', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usageevent',
            name='api_key_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='usageevent',
            name='units_consumed',
            field=models.PositiveIntegerField(),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(fields=['customer', 'timestamp'], name='usage_event_cust_ts'),
        ),
        migrations.AddIndex(
            model_name='usageevent',
            index=models.Index(fields=['customer', '-timestamp'], name='usage_event_cust_ts_desc'),
        ),
        migrations.CreateModel(
            name='UsageWindow',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('window_start', models.DateTimeField()),
                ('total_units', models.PositiveBigIntegerField(default=0)),
                ('event_count', models.PositiveIntegerField(default=0)),
                ('is_invoiced', models.BooleanField(db_index=True, default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usage_windows', to='customers.customer')),
            ],
            options={
                'unique_together': {('customer', 'window_start')},
                'indexes': [
                    models.Index(fields=['customer', 'window_start'], name='usage_window_cust_ws'),
                    models.Index(fields=['is_invoiced', 'window_start'], name='usage_window_invoiced'),
                ],
            },
        ),
    ]
