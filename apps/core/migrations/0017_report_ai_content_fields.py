from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_report_report_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='complaint_analysis',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='report',
            name='mood_analysis',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='report',
            name='technical_recommendations',
            field=models.TextField(blank=True, default=''),
        ),
    ]
