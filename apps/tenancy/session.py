from .models import Company, CompanyMembership


def get_active_memberships_for_user(user):
    return CompanyMembership.objects.select_related('company').filter(
        user=user,
        is_active=True,
        company__is_active=True,
    )


def resolve_default_company_id(user):
    if user.is_superuser:
        return None
    memberships = get_active_memberships_for_user(user)
    default_membership = memberships.filter(is_default=True).first()
    if default_membership:
        return default_membership.company_id
    first_membership = memberships.first()
    if first_membership:
        return first_membership.company_id
    return None


def user_has_company_access(user, company_id: int) -> bool:
    if user.is_superuser:
        return Company.objects.filter(id=company_id, is_active=True).exists()
    return get_active_memberships_for_user(user).filter(company_id=company_id).exists()


def get_membership_for_company(user, company_id: int):
    return get_active_memberships_for_user(user).filter(company_id=company_id).first()


def user_is_company_admin(user, company_id: int) -> bool:
    if user.is_superuser:
        return True
    membership = get_membership_for_company(user, company_id)
    if membership is None:
        return False
    return membership.role in CompanyMembership.ADMIN_ROLES
