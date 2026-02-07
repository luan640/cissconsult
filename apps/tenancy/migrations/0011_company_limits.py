from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('tenancy', '0005_company_address_city_company_address_complement_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='max_users',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='company',
            name='max_totems',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
