from django.db import migrations, models


DEFAULT_EMOJIS_BY_LABEL = {
    'muito bem': '😀',
    'bem': '🙂',
    'mais ou menos': '😐',
    'normal': '😌',
    'triste': '😟',
    'irritado': '😠',
    'sobrecarregado': '😩',
    'cansado': '😪',
    'desmotivado': '😞',
    'desapontado': '🙁',
    'estressado': '😣',
}

DEFAULT_EMOJI_BY_SENTIMENT = {
    'very_good': '😀',
    'good': '🙂',
    'neutral': '😐',
    'bad': '😟',
    'very_bad': '😠',
}


def fill_mood_type_emoji(apps, schema_editor):
    MoodType = apps.get_model('core', 'MoodType')
    for mood_type in MoodType.objects.all():
        label_key = (mood_type.label or '').strip().lower()
        emoji = DEFAULT_EMOJIS_BY_LABEL.get(label_key)
        if not emoji:
            emoji = DEFAULT_EMOJI_BY_SENTIMENT.get(mood_type.sentiment, '🙂')
        mood_type.emoji = emoji
        mood_type.save(update_fields=['emoji'])


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0013_alter_complaint_complaint_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='moodtype',
            name='emoji',
            field=models.CharField(default='🙂', max_length=8),
        ),
        migrations.RunPython(fill_mood_type_emoji, migrations.RunPython.noop),
    ]
