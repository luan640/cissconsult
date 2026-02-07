from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0021_campaign_uuid'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cpf_hash', models.CharField(max_length=64)),
                ('first_name', models.CharField(blank=True, max_length=120)),
                ('age', models.PositiveSmallIntegerField()),
                ('sex', models.CharField(blank=True, max_length=20)),
                ('responses', models.JSONField(blank=True, default=dict)),
                ('comments', models.TextField(blank=True)),
                ('completed_at', models.DateTimeField(auto_now_add=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='core.campaign')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='core_campaignresponse_set', to='tenancy.company')),
                ('department', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campaign_responses', to='core.department')),
                ('ghe', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='campaign_responses', to='core.ghe')),
            ],
            options={
                'db_table': 'campaign_responses',
            },
        ),
        migrations.AddConstraint(
            model_name='campaignresponse',
            constraint=models.UniqueConstraint(fields=('campaign', 'cpf_hash'), name='core_campaign_response_unique_cpf_per_campaign'),
        ),
    ]
