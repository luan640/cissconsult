from apps.tenancy.models import Company


def current_company(request):
    company_id = request.session.get('company_id')
    company_name = ''

    if company_id:
        company = Company.objects.filter(pk=company_id).only('name').first()
        if company:
            company_name = company.name

    return {
        'current_company_name': company_name,
        'current_company_id': company_id,
        'is_master': bool(getattr(request, 'user', None) and request.user.is_authenticated and request.user.is_superuser),
    }
