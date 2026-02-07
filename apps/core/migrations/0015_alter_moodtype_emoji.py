from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_moodtype_emoji'),
    ]

    operations = [
        migrations.AlterField(
            model_name='moodtype',
            name='emoji',
            field=models.CharField(default='🙂', max_length=32),
        ),
    ]
