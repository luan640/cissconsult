from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("masterdata", "0001_master_report_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="masterreportsettings",
            name="evaluation_representative_location",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
