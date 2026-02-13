from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Company
from .tasks import seed_company_defaults


@receiver(post_save, sender=Company)
def seed_default_totem_options_for_company(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        import django_rq
    except Exception:
        seed_company_defaults(instance.id)
        return

    def enqueue_seed():
        try:
            django_rq.enqueue(seed_company_defaults, instance.id)
        except Exception:
            seed_company_defaults(instance.id)

    from django.db import transaction

    transaction.on_commit(enqueue_seed)
