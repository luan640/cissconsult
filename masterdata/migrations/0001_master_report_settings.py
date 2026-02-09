from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='MasterReportSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('evaluation_representative_name', models.CharField(blank=True, max_length=255)),
            ],
            options={
                'db_table': 'master_report_settings',
            },
        ),
    ]

