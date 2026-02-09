from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_merge_20260208_0000'),
    ]

    operations = [
        migrations.CreateModel(
            name='TechnicalResponsible',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('education', models.CharField(max_length=255)),
                ('registration', models.CharField(max_length=80)),
                ('sort_order', models.PositiveSmallIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='core_technicalresponsible_set', to='tenancy.company')),
            ],
            options={
                'db_table': 'technical_responsibles',
                'ordering': ['sort_order', 'name'],
            },
        ),
    ]
