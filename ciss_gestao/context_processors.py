from apps.tenancy.models import Company
from apps.tenancy.session import get_membership_for_company


def current_company(request):
    company_id = request.session.get('company_id')
    consultancy_id = getattr(request, 'consultancy_id', None)
    company_name = ''
    user_role_label = ''

    if company_id:
        company = Company.objects.filter(
            pk=company_id,
            consultancy_id=consultancy_id,
        ).only('name').first() if consultancy_id else Company.objects.filter(
            pk=company_id,
        ).only('name').first()
        if company:
            company_name = company.name
        if request.user.is_authenticated:
            membership = get_membership_for_company(
                request.user,
                company_id,
                consultancy_id=consultancy_id,
            )
            if membership:
                user_role_label = membership.get_role_display()

    return {
        'current_company_name': company_name,
        'current_company_id': company_id,
        'is_master': bool(getattr(request, 'user', None) and request.user.is_authenticated and request.user.is_superuser),
        'user_role_label': user_role_label,
    }
