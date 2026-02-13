from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

from .context import reset_current_company_id, set_current_company_id
from .session import (
    get_active_memberships_for_user,
    resolve_default_company_id,
    user_has_company_access,
)


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
                if (not request.user.is_superuser) and (
                    not get_active_memberships_for_user(request.user).exists()
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
        session_company_id = request.session.get('company_id')
        if session_company_id:
            try:
                session_company_id = int(session_company_id)
            except (TypeError, ValueError):
                session_company_id = None

        if session_company_id and user_has_company_access(
            request.user,
            session_company_id,
        ):
            return session_company_id

        default_company_id = resolve_default_company_id(request.user)
        if default_company_id is None:
            return None
        request.session['company_id'] = default_company_id
        return default_company_id

    def _extract_company_id(self, request):
        header_name = settings.TENANCY_COMPANY_HEADER
        raw_company_id = request.headers.get(header_name)
        if raw_company_id is None:
            return None
        try:
            return int(raw_company_id)
        except ValueError as exc:
            raise PermissionDenied(f'Invalid {header_name} value.') from exc

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
