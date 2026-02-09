from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0011_company_limits'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='legal_representative_name',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]

