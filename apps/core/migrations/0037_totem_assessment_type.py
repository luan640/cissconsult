from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0036_campaignresponse_job_function'),
    ]

    operations = [
        migrations.AddField(
            model_name='totem',
            name='assessment_type',
            field=models.CharField(blank=True, default='setor', max_length=20),
        ),
    ]
