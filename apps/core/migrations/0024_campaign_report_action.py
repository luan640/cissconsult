from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_alter_campaignresponse_company'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignReportAction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('question_text', models.TextField()),
                ('measures', models.JSONField(blank=True, default=list)),
                ('implantation_months', models.JSONField(blank=True, default=list)),
                ('status', models.JSONField(blank=True, default=dict)),
                ('concluded_on', models.CharField(blank=True, max_length=20)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_actions', to='core.campaign')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='core_campaignreportaction_set', to='tenancy.company')),
            ],
            options={
                'db_table': 'campaign_report_actions',
            },
        ),
        migrations.AddConstraint(
            model_name='campaignreportaction',
            constraint=models.UniqueConstraint(fields=('campaign', 'question_text'), name='core_campaign_report_action_unique_question'),
        ),
    ]

