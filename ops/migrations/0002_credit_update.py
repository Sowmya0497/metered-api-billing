from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='credit',
            name='amount_cents',
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='credit',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='credit',
            name='actor',
            field=models.CharField(default='ops', max_length=255),
        ),
        migrations.RemoveField(
            model_name='credit',
            name='amount',
        ),
    ]
