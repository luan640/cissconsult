from .models import Company, CompanyMembership


def get_active_memberships_for_user(user, consultancy_id: int | None = None):
    queryset = CompanyMembership.objects.select_related('company').filter(
        user=user,
        is_active=True,
        company__is_active=True,
    )
    if consultancy_id is not None:
        queryset = queryset.filter(company__consultancy_id=consultancy_id)
    return queryset


def resolve_default_company_id(user, consultancy_id: int | None = None):
    if user.is_superuser:
        return None
    memberships = get_active_memberships_for_user(user, consultancy_id=consultancy_id)
    default_membership = memberships.filter(is_default=True).first()
    if default_membership:
        return default_membership.company_id
    first_membership = memberships.first()
    if first_membership:
        return first_membership.company_id
    return None


def user_has_company_access(
    user,
    company_id: int,
    consultancy_id: int | None = None,
) -> bool:
    if user.is_superuser:
        queryset = Company.objects.filter(id=company_id, is_active=True)
        if consultancy_id is not None:
            queryset = queryset.filter(consultancy_id=consultancy_id)
        return queryset.exists()
    return get_active_memberships_for_user(
        user,
        consultancy_id=consultancy_id,
    ).filter(company_id=company_id).exists()


def get_membership_for_company(
    user,
    company_id: int,
    consultancy_id: int | None = None,
):
    return get_active_memberships_for_user(
        user,
        consultancy_id=consultancy_id,
    ).filter(company_id=company_id).first()


def user_is_company_admin(
    user,
    company_id: int,
    consultancy_id: int | None = None,
) -> bool:
    if user.is_superuser:
        return True
    membership = get_membership_for_company(
        user,
        company_id,
        consultancy_id=consultancy_id,
    )
    if membership is None:
        return False
    return membership.role in CompanyMembership.ADMIN_ROLES
