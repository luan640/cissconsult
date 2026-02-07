from django.apps import AppConfig


class TenancyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenancy'
    label = 'tenancy'

    def ready(self) -> None:
        from . import checks  # noqa: F401
        from . import signals  # noqa: F401
