from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import AlertSetting, ComplaintType, MoodType

from .models import Company


DEFAULT_MOOD_TYPES = [
    ('Muito bem', '😀', 'very_good', 5),
    ('Bem', '🙂', 'good', 4),
    ('Mais ou menos', '😐', 'neutral', 3),
    ('Normal', '😌', 'neutral', 3),
    ('Triste', '😟', 'bad', 2),
    ('Irritado', '😠', 'very_bad', 1),
    ('Sobrecarregado', '😩', 'bad', 2),
    ('Cansado', '😪', 'bad', 2),
    ('Desmotivado', '😞', 'bad', 2),
    ('Desapontado', '🙁', 'bad', 2),
    ('Estressado', '😣', 'very_bad', 1),
]

DEFAULT_COMPLAINT_TYPES = [
    'Assédio moral',
    'Assédio sexual',
    'Discriminação',
    'Conduta antiética',
    'Violência psicológica',
    'Outro',
]


@receiver(post_save, sender=Company)
def seed_default_totem_options_for_company(sender, instance, created, **kwargs):
    if not created:
        return

    for label, emoji, sentiment, score in DEFAULT_MOOD_TYPES:
        MoodType.all_objects.get_or_create(
            company=instance,
            label=label,
            defaults={
                'emoji': emoji,
                'sentiment': sentiment,
                'mood_score': score,
                'is_active': True,
            },
        )

    for label in DEFAULT_COMPLAINT_TYPES:
        ComplaintType.all_objects.get_or_create(
            company=instance,
            label=label,
            defaults={
                'is_active': True,
            },
        )

    AlertSetting.all_objects.get_or_create(
        company=instance,
        defaults={
            'auto_alerts_enabled': True,
            'analysis_window_days': 30,
            'max_critical_complaints': 5,
            'max_negative_mood_percent': 35,
            'max_open_help_requests': 10,
            'is_active': True,
        },
    )
