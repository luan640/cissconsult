from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_campaign_report_settings_attachments'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='ghe',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='departments', to='core.ghe'),
        ),
    ]
