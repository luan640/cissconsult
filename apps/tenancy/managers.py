from django.db import models

from .context import get_current_company_id


class TenantQuerySet(models.QuerySet):
    def for_company(self, company_id: int):
        return self.filter(company_id=company_id)


class TenantManager(models.Manager):
    def get_queryset(self):
        queryset = TenantQuerySet(self.model, using=self._db)
        company_id = get_current_company_id()
        if company_id is None:
            return queryset.none()
        return queryset.for_company(company_id)
