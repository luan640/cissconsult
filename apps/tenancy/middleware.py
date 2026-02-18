from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

from .context import reset_current_company_id, set_current_company_id
from .models import Company, Consultancy
from .session import (
    get_active_memberships_for_user,
    resolve_default_company_id,
    user_has_company_access,
)


class ConsultancyHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        consultancy = self._resolve_consultancy(request)
        request.consultancy = consultancy
        request.consultancy_id = consultancy.id if consultancy else None
        return self.get_response(request)

    @staticmethod
    def _resolve_consultancy(request):
        host = (request.get_host() or '').split(':', 1)[0].strip().lower()
        if not host:
            return None

        base_domain = (settings.TENANCY_BASE_DOMAIN or '').strip().lower()
        if not base_domain:
            return None

        root_hosts = {base_domain, f'www.{base_domain}'}
        if host in root_hosts:
            return None
        if not host.endswith(f'.{base_domain}'):
            return None

        slug = host[: -(len(base_domain) + 1)].strip().lower()
        if not slug or '.' in slug:
            return None

        return Consultancy.objects.filter(
            slug=slug,
            is_active=True,
        ).first()


class CompanyContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            token = set_current_company_id(None)
            try:
                request.company_id = None
                return self.get_response(request)
            finally:
                reset_current_company_id(token)

        company_id = self._resolve_company_id(request)
        if company_id is None:
            if request.user.is_authenticated:
                if request.user.is_superuser:
                    token = set_current_company_id(None)
                    try:
                        request.company_id = None
                        return self.get_response(request)
                    finally:
                        reset_current_company_id(token)
                if (not request.user.is_superuser) and (
                    not get_active_memberships_for_user(
                        request.user,
                        consultancy_id=request.consultancy_id,
                    ).exists()
                ):
                    return render(request, 'errors/inactive_company.html', status=403)
                return self._redirect_to_company_select(request)
            token = set_current_company_id(None)
            try:
                request.company_id = None
                return self.get_response(request)
            finally:
                reset_current_company_id(token)

        token = set_current_company_id(company_id)
        try:
            request.company_id = company_id
            return self.get_response(request)
        finally:
            reset_current_company_id(token)

    def _resolve_company_id(self, request):
        if request.user.is_authenticated:
            return self._resolve_authenticated_company_id(request)
        return self._extract_company_id(request)

    def _resolve_authenticated_company_id(self, request):
        consultancy_id = request.consultancy_id
        session_company_id = request.session.get('company_id')
        if session_company_id:
            try:
                session_company_id = int(session_company_id)
            except (TypeError, ValueError):
                session_company_id = None

        if session_company_id and user_has_company_access(
            request.user,
            session_company_id,
            consultancy_id=consultancy_id,
        ):
            return session_company_id

        default_company_id = resolve_default_company_id(
            request.user,
            consultancy_id=consultancy_id,
        )
        if default_company_id is None:
            return None
        request.session['company_id'] = default_company_id
        return default_company_id

    def _extract_company_id(self, request):
        consultancy_id = request.consultancy_id
        header_name = settings.TENANCY_COMPANY_HEADER
        raw_company_id = request.headers.get(header_name)
        if raw_company_id is None:
            return None
        try:
            company_id = int(raw_company_id)
        except ValueError as exc:
            raise PermissionDenied(f'Invalid {header_name} value.') from exc
        if consultancy_id is not None:
            if request.user.is_authenticated:
                if not user_has_company_access(
                    request.user,
                    company_id,
                    consultancy_id=consultancy_id,
                ):
                    raise PermissionDenied(
                        'Company does not belong to active consultancy.',
                    )
            elif not Company.objects.filter(
                id=company_id,
                consultancy_id=consultancy_id,
                is_active=True,
            ).exists():
                raise PermissionDenied(
                    'Company does not belong to active consultancy.',
                )
        return company_id

    @staticmethod
    def _is_exempt(path: str) -> bool:
        return any(
            path.startswith(prefix)
            for prefix in settings.TENANCY_EXEMPT_PATH_PREFIXES
        )

    @staticmethod
    def _redirect_to_company_select(request):
        next_url = request.get_full_path()
        target = f"{reverse('company-select')}?next={quote(next_url, safe='/?:=&')}"
        response = redirect(target)
        if request.headers.get('HX-Request') == 'true':
            response.headers['HX-Redirect'] = target
        return response
