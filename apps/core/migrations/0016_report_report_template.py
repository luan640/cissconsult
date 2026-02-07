from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_alter_moodtype_emoji'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='report_template',
            field=models.CharField(
                choices=[
                    ('technical', 'RELATORIO TECNICO DE SAUDE MENTAL ORGANIZACIONAL'),
                    ('other', 'Outro relatorio'),
                ],
                default='technical',
                max_length=30,
            ),
        ),
    ]
