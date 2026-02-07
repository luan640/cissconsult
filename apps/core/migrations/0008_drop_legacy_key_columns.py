from django.db import migrations


def drop_legacy_key_columns(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    def column_exists(table_name, column_name):
        with connection.cursor() as cursor:
            if vendor == 'sqlite':
                cursor.execute(f"PRAGMA table_info('{table_name}')")
                return any(row[1] == column_name for row in cursor.fetchall())
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                [table_name, column_name],
            )
            return cursor.fetchone() is not None

    with connection.cursor() as cursor:
        if vendor == 'sqlite':
            for table_name in ('complaint_types', 'mood_types'):
                if not column_exists(table_name, 'key'):
                    continue

                cursor.execute(f"PRAGMA index_list('{table_name}')")
                indexes = cursor.fetchall()
                for index in indexes:
                    index_name = index[1]
                    cursor.execute(f"PRAGMA index_info('{index_name}')")
                    indexed_columns = [row[2] for row in cursor.fetchall()]
                    if 'key' in indexed_columns:
                        cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')

                cursor.execute(f'ALTER TABLE "{table_name}" DROP COLUMN "key"')
        else:
            cursor.execute('ALTER TABLE complaint_types DROP COLUMN IF EXISTS "key" CASCADE')
            cursor.execute('ALTER TABLE mood_types DROP COLUMN IF EXISTS "key" CASCADE')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0007_complainttype_moodtype'),
    ]

    operations = [
        migrations.RunPython(drop_legacy_key_columns, migrations.RunPython.noop),
    ]
