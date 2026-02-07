from uuid import uuid4

from django.db import migrations, models


def populate_campaign_uuids(apps, schema_editor):
    Campaign = apps.get_model('core', 'Campaign')
    for campaign in Campaign.objects.filter(uuid__isnull=True):
        campaign.uuid = uuid4()
        campaign.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_campaign_created_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='uuid',
            field=models.UUIDField(default=uuid4, editable=False, null=True, unique=True),
        ),
        migrations.RunPython(populate_campaign_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='campaign',
            name='uuid',
            field=models.UUIDField(default=uuid4, editable=False, unique=True),
        ),
    ]
