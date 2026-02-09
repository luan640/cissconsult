from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_remove_technical_responsible_company'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE technical_responsibles DROP COLUMN IF EXISTS company_id;",
            reverse_sql="ALTER TABLE technical_responsibles ADD COLUMN company_id integer NULL;",
        ),
    ]

