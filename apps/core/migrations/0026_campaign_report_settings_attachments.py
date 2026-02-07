from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_campaign_report_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaignreportsettings',
            name='attachments',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
