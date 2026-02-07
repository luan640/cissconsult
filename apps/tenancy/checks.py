from django.apps import apps
from django.core.checks import Error, Tags, register


@register(Tags.models)
def validate_company_field(app_configs=None, **kwargs):
    errors = []

    for model in apps.get_models():
        module_name = model.__module__
        if not module_name.startswith('apps.'):
            continue
        if model._meta.abstract or model._meta.proxy:
            continue
        if model._meta.app_label == 'tenancy' and model.__name__ == 'Company':
            continue
        if not any(field.name == 'company' for field in model._meta.fields):
            errors.append(
                Error(
                    f'Model {model.__name__} must define company_id.',
                    obj=model,
                    id='tenancy.E001',
                )
            )

    return errors
