from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_campaign_report_action'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignReportSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reevaluate_months', models.PositiveSmallIntegerField(default=3)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_settings', to='core.campaign')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='core_campaignreportsettings_set', to='tenancy.company')),
            ],
            options={
                'db_table': 'campaign_report_settings',
            },
        ),
        migrations.AddConstraint(
            model_name='campaignreportsettings',
            constraint=models.UniqueConstraint(fields=('campaign',), name='core_campaign_report_settings_unique_campaign'),
        ),
    ]

