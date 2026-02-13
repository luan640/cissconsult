import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse
from django.conf import settings
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.text import get_valid_filename
from django.views import View
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from datetime import date, datetime, timedelta
from uuid import uuid4
from io import BytesIO

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # library optional in local setup
    genai = None
    genai_types = None

from apps.core.models import (
    Alert,
    ComplaintActionHistory,
    AlertRecipient,
    AlertSetting,
    Campaign,
    CampaignReportSettings,
    CampaignReportAction,
    CampaignResponse,
    Complaint,
    ComplaintType,
    Department,
    GHE,
    JobFunction,
    HelpRequest,
    HelpRequestActionHistory,
    MoodRecord,
    MoodType,
    Report,
    StandardActionPlan,
    TechnicalResponsible,
    Totem,
)
from masterdata.models import MasterReportSettings
from apps.tenancy.models import Company, CompanyMembership
from apps.tenancy.session import (
    get_active_memberships_for_user,
    get_membership_for_company,
    resolve_default_company_id,
    user_has_company_access,
    user_is_company_admin,
)
from .report_pdf import build_campaign_report_pdf

try:
    import qrcode
except ImportError:  # optional dependency in local setup
    qrcode = None


def build_period_metrics(company_id, period_start, period_end, sentiment_labels):
    mood_qs = MoodRecord.all_objects.filter(
        company_id=company_id,
        record_date__gte=period_start,
        record_date__lte=period_end,
    )
    complaint_qs = Complaint.all_objects.filter(
        company_id=company_id,
        record_date__gte=period_start,
        record_date__lte=period_end,
    )
    help_qs = HelpRequest.all_objects.filter(
        company_id=company_id,
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    )

    top_sentiment = (
        mood_qs.values('sentiment')
        .annotate(total=Count('id'))
        .order_by('-total')
        .first()
    )
    complaint_status = (
        complaint_qs.values('complaint_status')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    mood_by_department = (
        mood_qs.values('department__name')
        .annotate(total=Count('id'))
        .order_by('-total', 'department__name')
    )
    complaint_by_totem = (
        complaint_qs.values('totem__name')
        .annotate(total=Count('id'))
        .order_by('-total', 'totem__name')
    )
    sentiment_order = ['very_good', 'good', 'neutral', 'bad', 'very_bad']
    sentiment_totals = {key: 0 for key in sentiment_order}
    for row in mood_qs.values('sentiment').annotate(total=Count('id')):
        if row['sentiment'] in sentiment_totals:
            sentiment_totals[row['sentiment']] = row['total']
    mood_total_count = sum(sentiment_totals.values())
    mood_distribution = []
    for key in sentiment_order:
        total = sentiment_totals[key]
        if total <= 0:
            continue
        percent = round((total * 100 / mood_total_count), 2) if mood_total_count else 0
        mood_distribution.append({
            'label': sentiment_labels.get(key, key),
            'total': total,
            'percent': percent,
        })
    mood_distribution = sorted(
        mood_distribution,
        key=lambda item: (-item['total'], item['label']),
    )

    complaint_type_map = {
        normalize_complaint_type_key(item.label): item.label
        for item in ComplaintType.all_objects.filter(company_id=company_id).only('label')
    }
    complaint_counts = {}
    for row in complaint_qs.values('category').annotate(total=Count('id')):
        category_key = row['category'] or ''
        label = complaint_type_map.get(
            category_key,
            complaint_type_display_name(category_key) or 'Nao informado',
        )
        complaint_counts[label] = complaint_counts.get(label, 0) + row['total']
    complaint_total_count = sum(complaint_counts.values())
    complaint_distribution = []
    for label, total in sorted(complaint_counts.items(), key=lambda item: (-item[1], item[0])):
        percent = round((total * 100 / complaint_total_count), 2) if complaint_total_count else 0
        complaint_distribution.append({
            'label': label,
            'total': total,
            'percent': percent,
        })
    complaint_distribution = sorted(
        complaint_distribution,
        key=lambda item: (-item['total'], item['label']),
    )

    return {
        'mood_count': mood_qs.count(),
        'complaint_count': complaint_qs.count(),
        'help_count': help_qs.count(),
        'top_sentiment': sentiment_labels.get(
            top_sentiment['sentiment'],
            'Sem registros',
        ) if top_sentiment else 'Sem registros',
        'complaint_status': complaint_status,
        'mood_by_department': mood_by_department,
        'complaint_by_totem': complaint_by_totem,
        'mood_distribution': mood_distribution,
        'complaint_distribution': complaint_distribution,
    }


def build_report_metrics(company_id, report, sentiment_labels):
    return build_period_metrics(
        company_id,
        report.period_start,
        report.period_end,
        sentiment_labels,
    )


def _compare_counts(metrics_a, metrics_b, key):
    a_val = int(metrics_a.get(key) or 0)
    b_val = int(metrics_b.get(key) or 0)
    delta = b_val - a_val
    percent = None if a_val == 0 else round((delta * 100 / a_val), 2)
    return {
        'a': a_val,
        'b': b_val,
        'delta': delta,
        'percent': percent,
    }


def build_report_comparison(metrics_a, metrics_b):
    return {
        'mood_count': _compare_counts(metrics_a, metrics_b, 'mood_count'),
        'complaint_count': _compare_counts(metrics_a, metrics_b, 'complaint_count'),
        'help_count': _compare_counts(metrics_a, metrics_b, 'help_count'),
        'top_sentiment': {
            'a': metrics_a.get('top_sentiment') or 'Sem registros',
            'b': metrics_b.get('top_sentiment') or 'Sem registros',
        },
        'mood_distribution': {
            'a': metrics_a.get('mood_distribution') or [],
            'b': metrics_b.get('mood_distribution') or [],
        },
        'complaint_distribution': {
            'a': metrics_a.get('complaint_distribution') or [],
            'b': metrics_b.get('complaint_distribution') or [],
        },
    }


def build_campaign_metrics(campaign):
    responses_qs = CampaignResponse.all_objects.filter(campaign=campaign)
    assessment_type = (campaign.company.assessment_type or '').strip().lower()
    use_departments = assessment_type == 'setor'
    group_label = 'Setores' if use_departments else 'GHE'
    group_id_field = 'department_id' if use_departments else 'ghe_id'
    group_name_map = {}
    if use_departments:
        department_ids = list(
            responses_qs.exclude(department_id__isnull=True)
            .values_list('department_id', flat=True)
            .distinct()
        )
        group_name_map = {
            department.id: department.name
            for department in Department.all_objects.filter(id__in=department_ids)
        }
    else:
        ghe_ids = list(
            responses_qs.exclude(ghe_id__isnull=True)
            .values_list('ghe_id', flat=True)
            .distinct()
        )
        group_name_map = {
            ghe.id: ghe.name for ghe in GHE.all_objects.filter(id__in=ghe_ids)
        }
    domain_totals = {
        key: {'sum': 0, 'count': 0}
        for key in CampaignReportView.DOMAIN_BY_STEP.keys()
    }
    group_totals = {}
    question_totals = {}
    overall_sum = 0
    overall_count = 0

    for response in responses_qs:
        answers_by_step = response.responses or {}
        for step_key, answers in answers_by_step.items():
            if step_key not in CampaignReportView.DOMAIN_BY_STEP or not answers:
                continue
            question_offset = CampaignReportView.STEP_OFFSETS.get(step_key, 0)
            question_texts = CampaignReportView.STEP_QUESTIONS.get(step_key, [])
            for idx, question_text in enumerate(question_texts):
                if idx >= len(answers):
                    break
                score = CampaignReportView.ANSWER_SCORE.get(answers[idx].get('answer', ''))
                if not score:
                    continue
                domain_totals[step_key]['sum'] += score
                domain_totals[step_key]['count'] += 1
                overall_sum += score
                overall_count += 1
                group_id = getattr(response, group_id_field, None)
                if group_id:
                    group_totals.setdefault(group_id, {'sum': 0, 'count': 0})
                    group_totals[group_id]['sum'] += score
                    group_totals[group_id]['count'] += 1
                question_number = question_offset + idx + 1
                question_key = (
                    question_number,
                    question_text,
                    CampaignReportView.DOMAIN_BY_STEP.get(step_key, ''),
                )
                question_totals.setdefault(question_key, {'sum': 0, 'count': 0})
                question_totals[question_key]['sum'] += score
                question_totals[question_key]['count'] += 1

    domains = []
    for step_key, label in CampaignReportView.DOMAIN_BY_STEP.items():
        count = domain_totals[step_key]['count']
        avg = (domain_totals[step_key]['sum'] / count) if count else 0
        percent = (avg / 5) * 100 if count else 0
        domains.append(
            {
                'label': label,
                'avg': round(avg, 1) if count else 0,
                'percent': round(percent, 1) if count else 0,
            }
        )

    overall_avg = (overall_sum / overall_count) if overall_count else 0
    overall_percent = (overall_avg / 5) * 100 if overall_count else 0
    overall_label = CampaignReportView._score_label(overall_avg) if overall_count else 'Sem dados'

    group_items = []
    for group_id, totals in group_totals.items():
        avg = (totals['sum'] / totals['count']) if totals['count'] else 0
        percent = (avg / 5) * 100 if totals['count'] else 0
        group_items.append(
            {
                'name': group_name_map.get(group_id, f'{group_label} {group_id}'),
                'avg': round(avg, 1) if totals['count'] else 0,
                'percent': round(percent, 1) if totals['count'] else 0,
            }
        )
    group_items = sorted(group_items, key=lambda item: item['name'])

    question_items = []
    for (question_number, question_text, domain_label), totals in question_totals.items():
        avg = (totals['sum'] / totals['count']) if totals['count'] else 0
        percent = (avg / 5) * 100 if totals['count'] else 0
        question_items.append(
            {
                'question_number': question_number,
                'text': question_text,
                'domain': domain_label,
                'avg': round(avg, 1) if totals['count'] else 0,
                'percent': round(percent, 1) if totals['count'] else 0,
            }
        )
    question_items = sorted(question_items, key=lambda item: item['question_number'])

    return {
        'responses_count': responses_qs.count(),
        'overall_avg': round(overall_avg, 1) if overall_count else 0,
        'overall_percent': round(overall_percent, 1) if overall_count else 0,
        'overall_label': overall_label,
        'domains': domains,
        'group_label': group_label,
        'groups': group_items,
        'questions': question_items,
    }


def build_campaign_comparison(metrics_a, metrics_b):
    domain_map_a = {item['label']: item for item in (metrics_a.get('domains') or [])}
    domain_map_b = {item['label']: item for item in (metrics_b.get('domains') or [])}
    domain_labels = sorted(set(domain_map_a.keys()) | set(domain_map_b.keys()))
    domain_rows = []
    for label in domain_labels:
        a_item = domain_map_a.get(label, {'avg': 0, 'percent': 0})
        b_item = domain_map_b.get(label, {'avg': 0, 'percent': 0})
        delta = round(b_item['percent'] - a_item['percent'], 1)
        percent = None if a_item['percent'] == 0 else round((delta * 100 / a_item['percent']), 1)
        domain_rows.append(
            {
                'label': label,
                'a': a_item,
                'b': b_item,
                'delta': delta,
                'percent': percent,
            }
        )

    return {
        'responses_count': _compare_counts(metrics_a, metrics_b, 'responses_count'),
        'overall_avg': _compare_counts(metrics_a, metrics_b, 'overall_avg'),
        'overall_percent': _compare_counts(metrics_a, metrics_b, 'overall_percent'),
        'overall_label': {
            'a': metrics_a.get('overall_label') or 'Sem dados',
            'b': metrics_b.get('overall_label') or 'Sem dados',
        },
        'domains': domain_rows,
        'group_label': metrics_a.get('group_label') or metrics_b.get('group_label') or 'GHE',
        'groups': build_named_comparison(metrics_a.get('groups'), metrics_b.get('groups')),
        'questions': build_question_comparison(metrics_a.get('questions'), metrics_b.get('questions')),
    }


def build_named_comparison(items_a, items_b):
    items_a = items_a or []
    items_b = items_b or []
    map_a = {item['name']: item for item in items_a}
    map_b = {item['name']: item for item in items_b}
    labels = sorted(set(map_a.keys()) | set(map_b.keys()))
    rows = []
    for label in labels:
        a_item = map_a.get(label, {'avg': 0, 'percent': 0})
        b_item = map_b.get(label, {'avg': 0, 'percent': 0})
        delta = round(b_item['percent'] - a_item['percent'], 1)
        percent = None if a_item['percent'] == 0 else round((delta * 100 / a_item['percent']), 1)
        rows.append(
            {
                'label': label,
                'a': a_item,
                'b': b_item,
                'delta': delta,
                'percent': percent,
            }
        )
    return rows


def build_question_comparison(items_a, items_b):
    items_a = items_a or []
    items_b = items_b or []
    map_a = {item['question_number']: item for item in items_a}
    map_b = {item['question_number']: item for item in items_b}
    question_numbers = sorted(set(map_a.keys()) | set(map_b.keys()))
    rows = []
    for number in question_numbers:
        a_item = map_a.get(number, {'avg': 0, 'percent': 0, 'text': '-', 'domain': '-'})
        b_item = map_b.get(number, {'avg': 0, 'percent': 0, 'text': '-', 'domain': '-'})
        delta = round(b_item['percent'] - a_item['percent'], 1)
        percent = None if a_item['percent'] == 0 else round((delta * 100 / a_item['percent']), 1)
        rows.append(
            {
                'question_number': number,
                'text': a_item.get('text') or b_item.get('text') or '-',
                'domain': a_item.get('domain') or b_item.get('domain') or '-',
                'a': a_item,
                'b': b_item,
                'delta': delta,
                'percent': percent,
            }
        )
    return rows


def healthz(request):
    return JsonResponse({'status': 'ok'})


def inactive_company(request, exception=None):
    return render(request, 'errors/inactive_company.html', status=403)


def campaign_qr(request, campaign_uuid):
    campaign = get_object_or_404(
        Campaign.all_objects.select_related('company'),
        uuid=campaign_uuid,
    )
    if qrcode is None:
        return HttpResponse('QR dependency not installed', status=501)

    qr_path = f"qrcodes/{campaign.uuid}.png"
    if default_storage.exists(qr_path):
        with default_storage.open(qr_path, 'rb') as handle:
            return HttpResponse(handle.read(), content_type='image/png')

    access_url = request.build_absolute_uri(reverse('campaigns-access', args=[campaign.uuid]))
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(access_url)
    qr.make(fit=True)
    image = qr.make_image(fill_color='black', back_color='white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    default_storage.save(qr_path, ContentFile(buffer.getvalue()))

    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='image/png')


def home(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


def is_ajax_request(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def is_master_user(request):
    return bool(getattr(request, 'user', None) and request.user.is_authenticated and request.user.is_superuser)


def get_campaigns_filters(request):
    company_id = (request.GET.get('company_id') or '').strip()
    status = (request.GET.get('status') or '').strip()
    return {
        'company_id': company_id,
        'status': status,
    }


def get_campaigns_queryset(filters):
    campaigns_qs = Campaign.all_objects.select_related('company').order_by('-start_date')
    company_id = filters.get('company_id') or ''
    if company_id.isdigit():
        campaigns_qs = campaigns_qs.filter(company_id=int(company_id))
    status = filters.get('status') or ''
    allowed_statuses = {value for value, _ in Campaign.Status.choices}
    if status in allowed_statuses:
        campaigns_qs = campaigns_qs.filter(status=status)
    return campaigns_qs


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label='E-mail',
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                'autofocus': True,
                'autocomplete': 'email',
                'placeholder': 'E-mail',
            }
        ),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'E-mail ou senha invalidos.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs.update(
            {
                'autocomplete': 'current-password',
                'placeholder': 'Senha',
            }
        )

    def clean(self):
        email = (self.cleaned_data.get('username') or '').strip().lower()
        password = self.cleaned_data.get('password')
        if email and password:
            user_model = get_user_model()
            matching_users = list(
                user_model._default_manager.filter(email__iexact=email)[:2]
            )
            if len(matching_users) != 1:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                )
            self.cleaned_data['username'] = matching_users[0].get_username()
        return super().clean()


class TenantLoginView(LoginView):
    template_name = 'auth/login.html'
    authentication_form = EmailAuthenticationForm

    def get_success_url(self):
        user = self.request.user
        if user.is_superuser:
            return reverse('master-dashboard')
        memberships = list(get_active_memberships_for_user(user))
        if not memberships:
            return reverse('company-select')
        if len(memberships) == 1:
            self.request.session['company_id'] = memberships[0].company_id
            return reverse('dashboard')

        default_company_id = resolve_default_company_id(user)
        if default_company_id is not None:
            self.request.session['company_id'] = default_company_id
            return reverse('dashboard')
        return reverse('company-select')


class DashboardView(LoginRequiredMixin, View):
    template_name = 'dashboard/index.html'
    SENTIMENT_LABELS = {
        'very_good': 'Muito bem',
        'good': 'Bem',
        'neutral': 'Neutro',
        'bad': 'Triste/Cansado',
        'very_bad': 'Irritado/Estressado',
    }

    def get(self, request):
        company_id = request.session.get('company_id')
        period_start, period_end = self._resolve_period(request)
        company_slug = None
        active_totems = []
        active_departments = []
        active_ghes = []
        if company_id:
            company = Company.objects.filter(id=company_id).only('slug').first()
            company_slug = company.slug if company else None
            active_totems = list(
                Totem.all_objects.filter(
                    company_id=company_id,
                    is_active=True,
                ).only('id', 'name', 'slug')
            )
            active_departments = list(
                Department.all_objects.filter(
                    company_id=company_id,
                    is_active=True,
                ).only('id', 'name', 'ghe_id')
            )
            active_ghes = list(
                GHE.all_objects.filter(
                    company_id=company_id,
                    is_active=True,
                ).only('id', 'name')
            )
        selected_totem_id, selected_totem_slug = self._resolve_totem_filter(request, active_totems)
        selected_department_id, selected_department_label = self._resolve_department_filter(request, active_departments)
        selected_ghe_id, selected_ghe_label = self._resolve_ghe_filter(request, active_ghes)
        metrics, chart_data = self._build_metrics_and_charts(
            company_id,
            period_start,
            period_end,
            selected_totem_id,
            selected_department_id,
            selected_ghe_id,
        )
        default_totem_slug = active_totems[0].slug if active_totems else None
        context = {
            'username': request.user.username,
            'company_id': company_id,
            'company_slug': company_slug,
            'active_totems': active_totems,
            'active_departments': active_departments,
            'active_ghes': active_ghes,
            'default_totem_slug': default_totem_slug,
            'metrics': metrics,
            'chart_data': chart_data,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'selected_totem_slug': selected_totem_slug,
            'selected_department_id': selected_department_id or '',
            'selected_ghe_id': selected_ghe_id or '',
            'can_manage_access': bool(
                company_id and user_is_company_admin(request.user, int(company_id))
            ),
            'is_master': request.user.is_superuser,
        }
        wants_partial = request.GET.get('partial') == '1' or request.headers.get('x-requested-with') == 'XMLHttpRequest'
        if wants_partial:
            return render(request, 'dashboard/_data_container.html', context)
        return render(request, self.template_name, context)

    @staticmethod
    def _resolve_period(request):
        today = date.today()
        default_start = today - timedelta(days=29)
        raw_start = (request.GET.get('start') or '').strip()
        raw_end = (request.GET.get('end') or '').strip()
        try:
            start = datetime.strptime(raw_start, '%Y-%m-%d').date() if raw_start else default_start
            end = datetime.strptime(raw_end, '%Y-%m-%d').date() if raw_end else today
        except ValueError:
            return default_start, today

        if start > end:
            return default_start, today
        if (end - start).days > 366:
            start = end - timedelta(days=366)
        return start, end

    @staticmethod
    def _resolve_totem_filter(request, active_totems):
        selected_slug = (request.GET.get('totem') or '').strip()
        if not selected_slug:
            return None, ''

        for totem in active_totems:
            if totem.slug == selected_slug:
                return totem.id, selected_slug
        return None, ''

    @staticmethod
    def _resolve_department_filter(request, active_departments):
        raw_value = (request.GET.get('department') or '').strip()
        if not raw_value:
            return None, ''
        try:
            department_id = int(raw_value)
        except (TypeError, ValueError):
            return None, ''
        for department in active_departments:
            if department.id == department_id:
                return department_id, department.name
        return None, ''

    @staticmethod
    def _resolve_ghe_filter(request, active_ghes):
        raw_value = (request.GET.get('ghe') or '').strip()
        if not raw_value:
            return None, ''
        try:
            ghe_id = int(raw_value)
        except (TypeError, ValueError):
            return None, ''
        for ghe in active_ghes:
            if ghe.id == ghe_id:
                return ghe_id, ghe.name
        return None, ''

    def _build_metrics_and_charts(self, company_id, period_start, period_end, totem_id=None, department_id=None, ghe_id=None):
        if not company_id:
            metrics = {
                'risk_level': 'Sem dados',
                'support_actions': 0,
                'mood_count_period': 0,
                'complaint_count_period': 0,
                'help_request_count_period': 0,
                'top_sentiment': 'Sem registros',
                'top_sentiment_overall': 'Sem registros',
                'totem_usage_period': 0,
            }
            return metrics, self._empty_chart_payload()

        mood_qs = MoodRecord.all_objects.filter(
            company_id=company_id,
            record_date__gte=period_start,
            record_date__lte=period_end,
        )
        complaint_qs = Complaint.all_objects.filter(
            company_id=company_id,
            record_date__gte=period_start,
            record_date__lte=period_end,
        )
        if totem_id:
            mood_qs = mood_qs.filter(totem_id=totem_id)
            complaint_qs = complaint_qs.filter(totem_id=totem_id)
        if department_id:
            mood_qs = mood_qs.filter(department_id=department_id)
        if ghe_id:
            mood_qs = mood_qs.filter(department__ghe_id=ghe_id)

        mood_count = mood_qs.count()
        complaint_count = complaint_qs.count()
        total_usage = mood_count + complaint_count
        help_request_qs = HelpRequest.all_objects.filter(
            company_id=company_id,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        )
        if totem_id:
            help_request_qs = help_request_qs.filter(totem_id=totem_id)
        help_request_count = help_request_qs.count()

        sentiment_count = (
            mood_qs.values('sentiment')
            .annotate(total=Count('id'))
            .order_by('-total')
            .first()
        )
        mood_overall_qs = MoodRecord.all_objects.filter(company_id=company_id)
        if totem_id:
            mood_overall_qs = mood_overall_qs.filter(totem_id=totem_id)
        if department_id:
            mood_overall_qs = mood_overall_qs.filter(department_id=department_id)
        if ghe_id:
            mood_overall_qs = mood_overall_qs.filter(department__ghe_id=ghe_id)
        sentiment_count_overall = (
            mood_overall_qs.values('sentiment')
            .annotate(total=Count('id'))
            .order_by('-total')
            .first()
        )

        if complaint_count >= 5:
            risk_level = 'Alto'
        elif complaint_count >= 2:
            risk_level = 'Medio'
        else:
            risk_level = 'Baixo'

        metrics = {
            'risk_level': risk_level,
            'support_actions': complaint_count,
            'mood_count_period': mood_count,
            'complaint_count_period': complaint_count,
            'help_request_count_period': help_request_count,
            'top_sentiment': self.SENTIMENT_LABELS.get(
                sentiment_count['sentiment'],
                'Sem registros',
            ) if sentiment_count else 'Sem registros',
            'top_sentiment_overall': self.SENTIMENT_LABELS.get(
                sentiment_count_overall['sentiment'],
                'Sem registros',
            ) if sentiment_count_overall else 'Sem registros',
            'totem_usage_period': total_usage,
        }
        charts = self._build_chart_payload(
            company_id,
            period_start,
            period_end,
            mood_qs,
            complaint_qs,
            totem_id=totem_id,
        )
        return metrics, charts

    @staticmethod
    def _empty_chart_payload():
        return {
            'mood_distribution': {'labels': [], 'values': []},
            'timeline': {'labels': [], 'mood_values': [], 'complaint_values': []},
            'weekday_frequency': {'labels': [], 'values': []},
            'period_comparison': {'labels': ['Periodo atual', 'Periodo anterior'], 'values': [0, 0]},
            'totem_usage': {'labels': [], 'values': []},
            'mood_by_department': {'labels': [], 'values': []},
            'mood_by_ghe': {'labels': [], 'values': []},
            'mood_distribution_by_department': {'labels': [], 'datasets': []},
            'complaint_by_department': {'labels': [], 'values': []},
            'complaint_by_type': {'labels': [], 'values': []},
        }

    def _build_chart_payload(
        self,
        company_id,
        period_start,
        period_end,
        mood_qs,
        complaint_qs,
        totem_id=None,
    ):
        weekday_labels = [
            'Seg',
            'Ter',
            'Qua',
            'Qui',
            'Sex',
            'Sab',
            'Dom',
        ]
        mood_by_day = (
            mood_qs.values('record_date')
            .annotate(total=Count('id'))
            .order_by('record_date')
        )
        complaint_by_day = (
            complaint_qs.values('record_date')
            .annotate(total=Count('id'))
            .order_by('record_date')
        )
        mood_by_date = {day['record_date']: day['total'] for day in mood_by_day}
        complaint_by_date = {day['record_date']: day['total'] for day in complaint_by_day}

        all_days = []
        cursor = period_start
        while cursor <= period_end:
            all_days.append(cursor)
            cursor += timedelta(days=1)

        timeline_labels = [day.strftime('%d/%m') for day in all_days]
        mood_timeline_values = [mood_by_date.get(day, 0) for day in all_days]
        complaint_timeline_values = [complaint_by_date.get(day, 0) for day in all_days]

        weekday_frequency_values = [0] * len(weekday_labels)
        for day in all_days:
            weekday_frequency_values[day.weekday()] += mood_by_date.get(day, 0)

        previous_period_start = period_start - timedelta(days=(period_end - period_start).days + 1)
        previous_period_end = period_start - timedelta(days=1)
        previous_mood_count = MoodRecord.all_objects.filter(
            company_id=company_id,
            record_date__gte=previous_period_start,
            record_date__lte=previous_period_end,
        ).count()
        previous_complaint_count = Complaint.all_objects.filter(
            company_id=company_id,
            record_date__gte=previous_period_start,
            record_date__lte=previous_period_end,
        ).count()

        totem_usage_qs = (
            mood_qs.values('totem__name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        totem_usage_labels = [
            item['totem__name'] or 'Sem totem'
            for item in totem_usage_qs
        ]
        totem_usage_values = [item['total'] for item in totem_usage_qs]

        mood_by_department_qs = (
            mood_qs.values('department__name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        mood_by_department_labels = [
            item['department__name'] or 'Sem setor'
            for item in mood_by_department_qs
        ]
        mood_by_department_values = [item['total'] for item in mood_by_department_qs]

        mood_by_ghe_qs = (
            mood_qs.values('department__ghe__name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        mood_by_ghe_labels = [
            item['department__ghe__name'] or 'Sem GHE'
            for item in mood_by_ghe_qs
        ]
        mood_by_ghe_values = [item['total'] for item in mood_by_ghe_qs]

        complaint_by_department_labels = []
        complaint_by_department_values = []

        complaint_by_type_qs = (
            Complaint.all_objects.filter(
                company_id=company_id,
                record_date__gte=period_start,
                record_date__lte=period_end,
            )
            .values('category')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        if totem_id:
            complaint_by_type_qs = complaint_by_type_qs.filter(totem_id=totem_id)
        complaint_by_type_labels = [
            dict(Complaint.CATEGORY_CHOICES).get(item['category'], item['category'])
            for item in complaint_by_type_qs
        ]
        complaint_by_type_values = [item['total'] for item in complaint_by_type_qs]

        mood_distribution_qs = (
            mood_qs.values('sentiment')
            .annotate(total=Count('id'))
            .order_by('sentiment')
        )
        mood_distribution_labels = [
            self.SENTIMENT_LABELS.get(item['sentiment'], item['sentiment'])
            for item in mood_distribution_qs
        ]
        mood_distribution_values = [item['total'] for item in mood_distribution_qs]

        mood_by_department_sentiment_qs = (
            mood_qs.values('department__name', 'sentiment')
            .annotate(total=Count('id'))
            .order_by('department__name')
        )
        department_sentiment_map = {}
        for item in mood_by_department_sentiment_qs:
            department = item['department__name'] or 'Sem setor'
            if department not in department_sentiment_map:
                department_sentiment_map[department] = {
                    key: 0 for key in self.SENTIMENT_LABELS.keys()
                }
            department_sentiment_map[department][item['sentiment']] = item['total']

        mood_distribution_by_department_labels = list(department_sentiment_map.keys())
        mood_distribution_by_department_datasets = []
        for sentiment_key, sentiment_label in self.SENTIMENT_LABELS.items():
            mood_distribution_by_department_datasets.append(
                {
                    'label': sentiment_label,
                    'values': [
                        department_sentiment_map[department][sentiment_key]
                        for department in mood_distribution_by_department_labels
                    ],
                }
            )

        current_total = mood_qs.count() + complaint_qs.count()
        return {
            'mood_distribution': {
                'labels': mood_distribution_labels,
                'values': mood_distribution_values,
            },
            'timeline': {
                'labels': timeline_labels,
                'mood_values': mood_timeline_values,
                'complaint_values': complaint_timeline_values,
            },
            'weekday_frequency': {
                'labels': weekday_labels,
                'values': weekday_frequency_values,
            },
            'period_comparison': {
                'labels': ['Periodo atual', 'Periodo anterior'],
                'values': [current_total, previous_mood_count + previous_complaint_count],
            },
            'totem_usage': {
                'labels': totem_usage_labels,
                'values': totem_usage_values,
            },
            'mood_by_department': {
                'labels': mood_by_department_labels,
                'values': mood_by_department_values,
            },
            'mood_by_ghe': {
                'labels': mood_by_ghe_labels,
                'values': mood_by_ghe_values,
            },
            'mood_distribution_by_department': {
                'labels': mood_distribution_by_department_labels,
                'datasets': mood_distribution_by_department_datasets,
            },
            'complaint_by_department': {
                'labels': complaint_by_department_labels,
                'values': complaint_by_department_values,
            },
            'complaint_by_type': {
                'labels': complaint_by_type_labels,
                'values': complaint_by_type_values,
            },
        }


class MasterRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Apenas usuario master pode acessar esta area.')
        return super().dispatch(request, *args, **kwargs)


class MasterDashboardView(MasterRequiredMixin, View):
    template_name = 'master/dashboard.html'

    def get(self, request):
        return render(request, self.template_name, self._build_context())

    def post(self, request):
        selected_company_id = request.POST.get('company_id')
        try:
            selected_company_id = int(selected_company_id)
        except (TypeError, ValueError):
            messages.error(request, 'Empresa invalida.')
            return render(request, self.template_name, self._build_context(), status=400)

        if not user_has_company_access(request.user, selected_company_id):
            messages.error(request, 'Voce nao possui acesso a esta empresa.')
            return render(request, self.template_name, self._build_context(), status=403)

        request.session['company_id'] = selected_company_id
        return redirect(reverse('dashboard'))

    @staticmethod
    def _build_context():
        today = timezone.localdate()
        companies_qs = Company.objects.order_by('name')
        active_companies_qs = companies_qs.filter(is_active=True)
        total_companies = companies_qs.count()
        active_companies = companies_qs.filter(is_active=True).count()
        campaigns_qs = Campaign.all_objects.all()
        total_campaigns = campaigns_qs.count()
        active_campaigns = campaigns_qs.filter(status=Campaign.Status.ACTIVE).count()
        paused_campaigns = campaigns_qs.filter(status=Campaign.Status.PAUSED).count()
        planned_campaigns = campaigns_qs.filter(status=Campaign.Status.PLANNED).count()
        finished_campaigns = campaigns_qs.filter(status=Campaign.Status.FINISHED).count()
        return {
            'active_menu': 'master-dashboard',
            'is_master': True,
            'companies': list(active_companies_qs.only('id', 'name')),
            'total_companies': total_companies,
            'active_companies': active_companies,
            'total_campaigns': total_campaigns,
            'active_campaigns': active_campaigns,
            'paused_campaigns': paused_campaigns,
            'planned_campaigns': planned_campaigns,
            'finished_campaigns': finished_campaigns,
        }


class MasterCompanyMetricsView(MasterRequiredMixin, View):
    def get(self, request):
        raw_company_id = (request.GET.get('company_id') or '').strip()
        try:
            company_id = int(raw_company_id)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Empresa invalida.'}, status=400)

        if not Company.objects.filter(id=company_id).exists():
            return JsonResponse({'error': 'Empresa invalida.'}, status=404)

        today = timezone.localdate()
        start_month = _month_start_offset(today, -11)
        month_cursor = start_month
        month_labels = []
        while month_cursor <= today.replace(day=1):
            month_labels.append(month_cursor.strftime('%m/%Y'))
            month_cursor = _month_start_offset(month_cursor, 1)

        month_counts = {
            item['month'].strftime('%m/%Y'): item['total']
            for item in CampaignResponse.all_objects.filter(
                company_id=company_id,
                completed_at__date__gte=start_month,
            )
            .annotate(month=TruncMonth('completed_at'))
            .values('month')
            .annotate(total=Count('id'))
        }
        history_values = [month_counts.get(label, 0) for label in month_labels]

        responses_qs = CampaignResponse.all_objects.filter(company_id=company_id)
        results = CampaignReportView()._build_results(responses_qs, {}, {})
        segment_labels = [item['label'] for item in results.get('domains', [])]
        segment_values = [float(item['percent'] or 0) for item in results.get('domains', [])]

        return JsonResponse(
            {
                'history': {
                    'labels': month_labels,
                    'values': history_values,
                },
                'segments': {
                    'labels': segment_labels,
                    'values': segment_values,
                },
            }
        )


def _month_start_offset(source_date, offset):
    month = source_date.month - 1 + offset
    year = source_date.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


class CompanySelectView(LoginRequiredMixin, View):
    template_name = 'auth/company_select.html'

    def get(self, request):
        if request.user.is_superuser:
            companies = list(
                Company.objects.filter(is_active=True).order_by('name').only('id', 'name')
            )
            return render(
                request,
                self.template_name,
                {
                    'companies': companies,
                    'is_master': True,
                    'next_url': request.GET.get('next') or reverse('dashboard'),
                },
            )
        memberships = list(get_active_memberships_for_user(request.user))
        return render(
            request,
            self.template_name,
            {
                'memberships': memberships,
                'is_master': False,
                'next_url': request.GET.get('next') or reverse('dashboard'),
            },
        )

    def post(self, request):
        selected_company_id = request.POST.get('company_id')
        try:
            selected_company_id = int(selected_company_id)
        except (TypeError, ValueError):
            return self._render_with_error(request, 'Empresa invalida.')

        if not user_has_company_access(request.user, selected_company_id):
            return render(request, 'errors/inactive_company.html', status=403)

        request.session['company_id'] = selected_company_id
        next_url = request.POST.get('next_url') or reverse('dashboard')
        return redirect(next_url)

    def _render_with_error(self, request, message):
        if request.user.is_superuser:
            companies = list(
                Company.objects.filter(is_active=True).order_by('name').only('id', 'name')
            )
            if not companies:
                return render(request, 'errors/inactive_company.html', status=403)
            return render(
                request,
                self.template_name,
                {
                    'companies': companies,
                    'is_master': True,
                    'next_url': request.POST.get('next_url') or reverse('dashboard'),
                    'error': message,
                },
                status=400,
            )
        memberships = list(get_active_memberships_for_user(request.user))
        return render(
            request,
            self.template_name,
            {
                'memberships': memberships,
                'is_master': False,
                'next_url': request.POST.get('next_url') or reverse('dashboard'),
                'error': message,
            },
            status=400,
        )


class CompanyListView(MasterRequiredMixin, View):
    template_name = 'companies/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        companies_qs = Company.objects.order_by('name')
        search_name = (request.GET.get('name') or '').strip()
        selected_status = (request.GET.get('status') or '').strip().lower()
        if search_name:
            companies_qs = companies_qs.filter(name=search_name)
        if selected_status == 'active':
            companies_qs = companies_qs.filter(is_active=True)
        elif selected_status == 'inactive':
            companies_qs = companies_qs.filter(is_active=False)
        page_obj = paginate_queryset(request, companies_qs)
        companies_filter_options = list(Company.objects.order_by('name').only('id', 'name'))
        context = {
            'companies': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'search_name': search_name,
            'selected_status': selected_status,
            'companies_filter_options': companies_filter_options,
            'active_menu': 'companies',
            'is_master': True,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'companies/_table_container.html', context)
        return render(request, self.template_name, context)


class CompanyCreateView(MasterRequiredMixin, View):
    def post(self, request):
        form = CompanyForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_companies_table(request)
            return redirect('companies-list')

        name = (form.cleaned_data['name'] or '').strip()
        if not name:
            messages.error(request, 'Nome da empresa e obrigatorio.')
            if is_ajax_request(request):
                return render_companies_table(request)
            return redirect('companies-list')

        cnpj = form.cleaned_data['cnpj']
        if Company.objects.filter(cnpj=cnpj).exists():
            messages.error(request, 'Ja existe empresa com este CNPJ.')
            if is_ajax_request(request):
                return render_companies_table(request)
            return redirect('companies-list')

        base_slug = slugify(name) or uuid4().hex[:8]
        final_slug = base_slug
        counter = 1
        while Company.objects.filter(slug=final_slug).exists():
            counter += 1
            final_slug = f'{base_slug}-{counter}'

        create_is_active = True
        if 'is_active' in request.POST:
            create_is_active = form.cleaned_data.get('is_active', False)

        Company.objects.create(
            name=name,
            legal_name=(form.cleaned_data['legal_name'] or '').strip(),
            legal_representative_name=(form.cleaned_data['legal_representative_name'] or '').strip(),
            responsible_email=(form.cleaned_data.get('responsible_email') or '').strip(),
            cnpj=cnpj,
            assessment_type=form.cleaned_data.get('assessment_type') or '',
            cnae=(form.cleaned_data.get('cnae') or '').strip(),
            risk_level=form.cleaned_data.get('risk_level') or 1,
            employee_count=form.cleaned_data['employee_count'],
            max_users=form.cleaned_data['max_users'],
            max_totems=form.cleaned_data['max_totems'],
            address_street=(form.cleaned_data['address_street'] or '').strip(),
            address_number=(form.cleaned_data['address_number'] or '').strip(),
            address_complement=(form.cleaned_data['address_complement'] or '').strip(),
            address_neighborhood=(form.cleaned_data['address_neighborhood'] or '').strip(),
            address_city=(form.cleaned_data['address_city'] or '').strip(),
            address_state=form.cleaned_data['address_state'],
            address_zipcode=(form.cleaned_data['address_zipcode'] or '').strip(),
            logo=form.cleaned_data.get('logo'),
            slug=final_slug,
            unit_type=form.cleaned_data.get('unit_type') or '',
            unit_name=(form.cleaned_data.get('unit_name') or '').strip(),
            is_active=create_is_active,
        )
        cache.clear()
        messages.success(request, 'Empresa cadastrada com sucesso.')
        if is_ajax_request(request):
            return render_companies_table(request)
        return redirect('companies-list')


class CompanyUpdateView(MasterRequiredMixin, View):
    def post(self, request, company_id):
        company = get_object_or_404(Company, pk=company_id)
        form = CompanyForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_companies_table(request)
            return redirect('companies-list')

        name = (form.cleaned_data['name'] or '').strip()
        if not name:
            messages.error(request, 'Nome da empresa e obrigatorio.')
            if is_ajax_request(request):
                return render_companies_table(request)
            return redirect('companies-list')

        cnpj = form.cleaned_data['cnpj']
        if Company.objects.filter(cnpj=cnpj).exclude(pk=company.id).exists():
            messages.error(request, 'Ja existe empresa com este CNPJ.')
            if is_ajax_request(request):
                return render_companies_table(request)
            return redirect('companies-list')

        company.name = name
        company.legal_name = (form.cleaned_data['legal_name'] or '').strip()
        company.legal_representative_name = (form.cleaned_data['legal_representative_name'] or '').strip()
        company.responsible_email = (form.cleaned_data.get('responsible_email') or '').strip()
        company.cnpj = cnpj
        company.assessment_type = form.cleaned_data.get('assessment_type') or ''
        company.cnae = (form.cleaned_data.get('cnae') or '').strip()
        company.risk_level = form.cleaned_data.get('risk_level') or 1
        company.employee_count = form.cleaned_data['employee_count']
        company.max_users = form.cleaned_data['max_users']
        company.max_totems = form.cleaned_data['max_totems']
        company.address_street = (form.cleaned_data['address_street'] or '').strip()
        company.address_number = (form.cleaned_data['address_number'] or '').strip()
        company.address_complement = (form.cleaned_data['address_complement'] or '').strip()
        company.address_neighborhood = (form.cleaned_data['address_neighborhood'] or '').strip()
        company.address_city = (form.cleaned_data['address_city'] or '').strip()
        company.address_state = form.cleaned_data['address_state']
        company.address_zipcode = (form.cleaned_data['address_zipcode'] or '').strip()
        company.unit_type = form.cleaned_data.get('unit_type') or ''
        company.unit_name = (form.cleaned_data.get('unit_name') or '').strip()
        if 'is_active' in request.POST:
            company.is_active = form.cleaned_data.get('is_active', False)
        if form.cleaned_data.get('logo'):
            company.logo = form.cleaned_data['logo']
        company.save()
        cache.clear()
        messages.success(request, 'Empresa atualizada com sucesso.')
        if is_ajax_request(request):
            return render_companies_table(request)
        return redirect('companies-list')


class CompanyDeleteView(MasterRequiredMixin, View):
    def post(self, request, company_id):
        company = get_object_or_404(Company, pk=company_id)
        company.is_active = not company.is_active
        company.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if company.is_active:
            messages.success(request, 'Empresa ativada com sucesso.')
        else:
            messages.success(request, 'Empresa desativada com sucesso.')
        return redirect('companies-list')


class CampaignListView(MasterRequiredMixin, View):
    template_name = 'campaigns/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        filters = get_campaigns_filters(request)
        campaigns_qs = get_campaigns_queryset(filters)
        page_obj = paginate_queryset(request, campaigns_qs, per_page=15)
        companies = list(Company.objects.order_by('name').only('id', 'name'))
        context = {
            'campaigns': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'companies': companies,
            'active_menu': 'campaigns',
            'is_master': True,
            'status_choices': Campaign.Status.choices,
            'selected_company_id': filters['company_id'],
            'selected_status': filters['status'],
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'campaigns/_table_container.html', context)
        return render(request, self.template_name, context)


class CampaignCreateView(MasterRequiredMixin, View):
    def post(self, request):
        form = CampaignForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_campaigns_table(request)
            return redirect('campaigns-list')

        company = get_object_or_404(Company, pk=form.cleaned_data['company_id'])
        Campaign.all_objects.create(
            company=company,
            title=(form.cleaned_data['title'] or '').strip(),
            start_date=form.cleaned_data['start_date'],
            end_date=form.cleaned_data['end_date'],
            status=form.cleaned_data['status'],
            created_by=request.user,
        )
        cache.clear()
        messages.success(request, 'Campanha criada com sucesso.')
        if is_ajax_request(request):
            return render_campaigns_table(request)
        return redirect('campaigns-list')


class CampaignUpdateView(MasterRequiredMixin, View):
    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign.all_objects.select_related('company'), pk=campaign_id)
        form = CampaignForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_campaigns_table(request)
            return redirect('campaigns-list')

        company = get_object_or_404(Company, pk=form.cleaned_data['company_id'])
        campaign.company = company
        campaign.title = (form.cleaned_data['title'] or '').strip()
        campaign.start_date = form.cleaned_data['start_date']
        campaign.end_date = form.cleaned_data['end_date']
        campaign.status = form.cleaned_data['status']
        campaign.save()
        cache.clear()
        messages.success(request, 'Campanha atualizada com sucesso.')
        if is_ajax_request(request):
            return render_campaigns_table(request)
        return redirect('campaigns-list')


class CampaignDeleteView(MasterRequiredMixin, View):
    def post(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, pk=campaign_id)
        campaign.delete()
        cache.clear()
        messages.success(request, 'Campanha removida com sucesso.')
        if is_ajax_request(request):
            return render_campaigns_table(request)
        return redirect('campaigns-list')


class MasterTechnicalSettingsView(MasterRequiredMixin, View):
    template_name = 'master/technical_settings.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        report_settings = ensure_master_report_settings()
        responsibles_qs = TechnicalResponsible.objects.filter(
            is_active=True
        ).order_by('sort_order', 'name')
        page_obj = paginate_queryset(request, responsibles_qs, per_page=15)
        company = None
        context = {
            'technical_responsibles': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'active_menu': 'master-settings',
            'is_master': True,
            'report_settings': report_settings,
            'company': company,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'master/_technical_table_container.html', context)
        return render(request, self.template_name, context)


class TechnicalResponsibleCreateView(MasterRequiredMixin, View):
    def post(self, request):
        form = TechnicalResponsibleForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_technical_responsibles_table(request)
            return redirect('master-settings')

        name = (form.cleaned_data['name'] or '').strip()
        education = (form.cleaned_data['education'] or '').strip()
        registration = (form.cleaned_data['registration'] or '').strip()
        sort_order = form.cleaned_data.get('sort_order') or 0
        if not name or not education or not registration:
            messages.error(request, 'Preencha nome, formação e registro.')
            if is_ajax_request(request):
                return render_technical_responsibles_table(request)
            return redirect('master-settings')

        TechnicalResponsible.objects.create(
            name=name,
            education=education,
            registration=registration,
            sort_order=sort_order,
            is_active=True,
        )
        cache.clear()
        messages.success(request, 'Responsável técnico criado com sucesso.')
        if is_ajax_request(request):
            return render_technical_responsibles_table(request)
        return redirect('master-settings')


class TechnicalResponsibleUpdateView(MasterRequiredMixin, View):
    def post(self, request, responsible_id):
        responsible = get_object_or_404(
            TechnicalResponsible,
            pk=responsible_id,
        )
        form = TechnicalResponsibleForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_technical_responsibles_table(request)
            return redirect('master-settings')

        name = (form.cleaned_data['name'] or '').strip()
        education = (form.cleaned_data['education'] or '').strip()
        registration = (form.cleaned_data['registration'] or '').strip()
        sort_order = form.cleaned_data.get('sort_order') or 0
        if not name or not education or not registration:
            messages.error(request, 'Preencha nome, formação e registro.')
            if is_ajax_request(request):
                return render_technical_responsibles_table(request)
            return redirect('master-settings')

        responsible.name = name
        responsible.education = education
        responsible.registration = registration
        responsible.sort_order = sort_order
        responsible.is_active = form.cleaned_data['is_active']
        responsible.save()
        cache.clear()
        messages.success(request, 'Responsável técnico atualizado com sucesso.')
        if is_ajax_request(request):
            return render_technical_responsibles_table(request)
        return redirect('master-settings')


class TechnicalResponsibleDeleteView(MasterRequiredMixin, View):
    def post(self, request, responsible_id):
        responsible = get_object_or_404(
            TechnicalResponsible,
            pk=responsible_id,
        )
        responsible.is_active = not responsible.is_active
        responsible.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if responsible.is_active:
            messages.success(request, 'Responsável técnico ativado com sucesso.')
        else:
            messages.success(request, 'Responsável técnico desativado com sucesso.')
        if is_ajax_request(request):
            return render_technical_responsibles_table(request)
        return redirect('master-settings')


class TechnicalResponsibleRemoveView(MasterRequiredMixin, View):
    def post(self, request, responsible_id):
        responsible = get_object_or_404(
            TechnicalResponsible,
            pk=responsible_id,
        )
        responsible.delete()
        cache.clear()
        messages.success(request, 'Responsável técnico excluído com sucesso.')
        if is_ajax_request(request):
            return render_technical_responsibles_table(request)
        return redirect('master-settings')


class MasterReportSettingsUpdateView(MasterRequiredMixin, View):
    def post(self, request):
        report_settings = ensure_master_report_settings()
        form = MasterReportSettingsForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            return redirect('master-settings')

        report_settings.evaluation_representative_name = (
            form.cleaned_data['evaluation_representative_name'] or ''
        ).strip()
        report_settings.evaluation_representative_location = (
            form.cleaned_data['evaluation_representative_location'] or ''
        ).strip()
        report_settings.save()
        cache.clear()
        messages.success(request, 'Representante legal atualizado com sucesso.')
        return redirect('master-settings')


class CampaignAccessView(View):
    template_name = 'campaigns/access.html'
    questions_template_name = 'campaigns/step2.html'
    questions_step3_template_name = 'campaigns/step3.html'
    questions_step4_template_name = 'campaigns/step4.html'
    questions_step5_template_name = 'campaigns/step5.html'
    questions_step6_template_name = 'campaigns/step6.html'
    questions_step7_template_name = 'campaigns/step7.html'
    questions_step8_template_name = 'campaigns/step8.html'
    questions_step9_template_name = 'campaigns/step9.html'
    questions_step10_template_name = 'campaigns/step10.html'
    SESSION_KEY = 'campaign_response'

    def get(self, request, campaign_uuid):
        context = self._build_context(campaign_uuid)
        status = context['campaign'].status
        if status == Campaign.Status.PAUSED:
            return render(request, 'campaigns/paused.html', context)
        if status == Campaign.Status.PLANNED:
            return render(request, 'campaigns/planned.html', context)
        if status == Campaign.Status.FINISHED:
            return render(request, 'campaigns/finished.html', context)
        step = (request.GET.get('step') or '').strip()
        if step == '10':
            return render(request, self.questions_step10_template_name, self._build_step10_context(context))

        wizard_context = self._build_wizard_context(context)
        wizard_context['initial_step'] = int(step) if step.isdigit() and 1 <= int(step) <= 9 else 1
        return render(request, 'campaigns/wizard.html', wizard_context)

    def _build_wizard_context(self, base_context):
        steps = []
        step2 = self._build_step2_context(base_context)
        step3 = self._build_step3_context(base_context)
        step4 = self._build_step4_context(base_context)
        step5 = self._build_step5_context(base_context)
        step6 = self._build_step6_context(base_context)
        step7 = self._build_step7_context(base_context)
        step8 = self._build_step8_context(base_context)
        step9 = self._build_step9_context(base_context)

        steps.append({'step': 2, **step2})
        steps.append({'step': 3, **step3})
        steps.append({'step': 4, **step4})
        steps.append({'step': 5, **step5})
        steps.append({'step': 6, **step6})
        steps.append({'step': 7, **step7})
        steps.append({'step': 8, **step8})

        return {
            **base_context,
            'steps': steps,
            'step9': step9,
        }

    def post(self, request, campaign_uuid):
        context = self._build_context(campaign_uuid)
        status = context['campaign'].status
        if status == Campaign.Status.PAUSED:
            return render(request, 'campaigns/paused.html', context)
        if status == Campaign.Status.PLANNED:
            return render(request, 'campaigns/planned.html', context)
        if status == Campaign.Status.FINISHED:
            return render(request, 'campaigns/finished.html', context)
        step = (request.POST.get('step') or '1').strip()
        campaign = context['campaign']

        if step == '1':
            cpf = (request.POST.get('cpf') or '').strip()
            age = (request.POST.get('age') or '').strip()
            ghe_id = (request.POST.get('ghe_id') or '').strip()
            department_id = (request.POST.get('department_id') or '').strip()
            job_function_id = (request.POST.get('job_function_id') or '').strip()
            first_name = (request.POST.get('first_name') or '').strip()
            sex = (request.POST.get('sex') or '').strip()
            assessment_type = (campaign.company.assessment_type or '').strip().upper()
            use_ghe = assessment_type != 'SETOR'

            cpf_digits = re.sub(r'\D', '', cpf)
            errors = []
            if len(cpf_digits) != 11:
                errors.append('CPF invalido.')
            if not age.isdigit() or int(age) <= 0:
                errors.append('Idade invalida.')
            if use_ghe:
                if not ghe_id:
                    errors.append('Informe o GHE.')
                if not department_id:
                    errors.append('Informe o cargo/funcao.')
            else:
                if not department_id:
                    errors.append('Informe o setor.')
                if not job_function_id:
                    errors.append('Informe o cargo/funcao.')
                ghe_id = ''

            cpf_hash = self._hash_cpf(campaign.uuid, cpf_digits) if cpf_digits else ''
            if cpf_hash and CampaignResponse.all_objects.filter(campaign=campaign, cpf_hash=cpf_hash).exists():
                errors.append('Este CPF ja foi utilizado nesta avaliacao.')

            if errors:
                messages.error(request, ' | '.join(errors))
                return render(request, self.template_name, context, status=400)

            self._store_session_data(
                request,
                campaign.uuid,
                {
                    'cpf_hash': cpf_hash,
                    'first_name': first_name,
                    'age': int(age),
                    'sex': sex,
                    'ghe_id': int(ghe_id) if ghe_id else None,
                    'department_id': int(department_id),
                    'job_function_id': int(job_function_id) if job_function_id else None,
                    'responses': {},
                    'comments': '',
                },
            )
            return redirect(f"{reverse('campaigns-access', args=[campaign.uuid])}?step=2")

        session_data = self._get_session_data(request, campaign.uuid)
        if not session_data:
            messages.error(request, 'Inicie a avaliacao novamente.')
            return redirect(reverse('campaigns-access', args=[campaign.uuid]))

        if step in {'2', '3', '4', '5', '6', '7', '8'}:
            step_info = self._get_step_context(step, context)
            questions = step_info['context']['questions']
            answers = self._collect_answers(request, questions)
            if answers is None:
                messages.error(request, 'Responda todas as perguntas para continuar.')
                return render(request, step_info['template'], step_info['context'], status=400)

            session_data['responses'][f'step{step}'] = answers
            self._store_session_data(request, campaign.uuid, session_data)
            next_step = str(int(step) + 1)
            return redirect(f"{reverse('campaigns-access', args=[campaign.uuid])}?step={next_step}")

        if step == '9':
            local_payload = (request.POST.get('local_payload') or '').strip()
            if local_payload:
                try:
                    payload = json.loads(local_payload)
                except json.JSONDecodeError:
                    payload = {}
                responses_payload = payload.get('responses') if isinstance(payload, dict) else None
                if isinstance(responses_payload, dict) and responses_payload:
                    session_data['responses'] = responses_payload
                if not (request.POST.get('comments') or '').strip():
                    payload_comments = (payload.get('comments') if isinstance(payload, dict) else '') or ''
                    session_data['comments'] = str(payload_comments).strip()
                if not session_data:
                    session_data = self._build_session_from_payload(payload, campaign)
                    if session_data is None:
                        messages.error(request, 'Inicie a avaliacao novamente.')
                        return redirect(reverse('campaigns-access', args=[campaign.uuid]))

            comments = (request.POST.get('comments') or session_data.get('comments') or '').strip()
            session_data['comments'] = comments
            self._store_session_data(request, campaign.uuid, session_data)

            try:
                CampaignResponse.all_objects.create(
                    company=campaign.company,
                    campaign=campaign,
                    cpf_hash=session_data['cpf_hash'],
                    first_name=session_data.get('first_name', ''),
                    age=session_data.get('age', 0),
                    sex=session_data.get('sex', ''),
                    ghe_id=session_data.get('ghe_id'),
                    department_id=session_data.get('department_id'),
                    job_function_id=session_data.get('job_function_id'),
                    responses=session_data.get('responses', {}),
                    comments=session_data.get('comments', ''),
                )
            except Exception:
                messages.error(request, 'Nao foi possivel registrar sua avaliacao. Tente novamente.')
                return render(request, self.questions_step9_template_name, self._build_step9_context(context), status=400)

            self._clear_session_data(request, campaign.uuid)
            return redirect(f"{reverse('campaigns-access', args=[campaign.uuid])}?step=10")

        messages.error(request, 'Etapa invalida.')
        return redirect(reverse('campaigns-access', args=[campaign.uuid]))

    @staticmethod
    def _build_context(campaign_uuid):
        campaign = get_object_or_404(
            Campaign.all_objects.select_related('company'),
            uuid=campaign_uuid,
        )
        assessment_type = (campaign.company.assessment_type or '').strip().upper()
        use_ghe = assessment_type != 'SETOR'
        ghes = list(GHE.all_objects.filter(company_id=campaign.company_id, is_active=True).order_by('name'))
        departments = list(Department.all_objects.filter(company_id=campaign.company_id, is_active=True).order_by('name'))
        return {
            'campaign': campaign,
            'company': campaign.company,
            'assessment_type': assessment_type,
            'use_ghe': use_ghe,
            'ghes': ghes,
            'departments': departments,
        }

    def _get_step_context(self, step, base_context):
        if step == '2':
            return {'template': self.questions_template_name, 'context': self._build_step2_context(base_context)}
        if step == '3':
            return {'template': self.questions_step3_template_name, 'context': self._build_step3_context(base_context)}
        if step == '4':
            return {'template': self.questions_step4_template_name, 'context': self._build_step4_context(base_context)}
        if step == '5':
            return {'template': self.questions_step5_template_name, 'context': self._build_step5_context(base_context)}
        if step == '6':
            return {'template': self.questions_step6_template_name, 'context': self._build_step6_context(base_context)}
        if step == '7':
            return {'template': self.questions_step7_template_name, 'context': self._build_step7_context(base_context)}
        if step == '8':
            return {'template': self.questions_step8_template_name, 'context': self._build_step8_context(base_context)}
        return {'template': self.questions_template_name, 'context': self._build_step2_context(base_context)}

    @staticmethod
    def _collect_answers(request, questions):
        answers = []
        for idx, question in enumerate(questions, start=1):
            answer = (request.POST.get(f'q{idx}') or '').strip()
            if not answer:
                return None
            answers.append({'question': question, 'answer': answer})
        return answers

    @staticmethod
    def _answers_to_map(answers):
        if not answers:
            return {}
        return {str(idx): item.get('answer') for idx, item in enumerate(answers, start=1)}

    def _attach_saved_answers(self, request, campaign_uuid, step, step_context):
        session_data = self._get_session_data(request, campaign_uuid)
        saved = None
        if session_data:
            saved = session_data.get('responses', {}).get(f'step{step}')
        answers_map = self._answers_to_map(saved)
        question_items = [
            {'text': question, 'answer': answers_map.get(str(idx), '')}
            for idx, question in enumerate(step_context.get('questions', []), start=1)
        ]
        return {**step_context, 'question_items': question_items}

    def _attach_saved_comment(self, request, campaign_uuid, step_context):
        session_data = self._get_session_data(request, campaign_uuid)
        saved_comment = ''
        if session_data:
            saved_comment = session_data.get('comments', '')
        return {**step_context, 'saved_comment': saved_comment}

    @staticmethod
    def _hash_cpf(campaign_uuid, cpf_digits):
        payload = f'{campaign_uuid}:{cpf_digits}'.encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _build_session_from_payload(payload, campaign):
        if not isinstance(payload, dict):
            return None
        meta = payload.get('meta') or {}
        cpf = str(meta.get('cpf') or '').strip()
        age = str(meta.get('age') or '').strip()
        ghe_id = str(meta.get('ghe_id') or '').strip()
        department_id = str(meta.get('department_id') or '').strip()
        job_function_id = str(meta.get('job_function_id') or '').strip()
        first_name = str(meta.get('first_name') or '').strip()
        sex = str(meta.get('sex') or '').strip()

        cpf_digits = re.sub(r'\D', '', cpf)
        if len(cpf_digits) != 11:
            return None
        if not age.isdigit() or int(age) <= 0:
            return None

        assessment_type = (campaign.company.assessment_type or '').strip().upper()
        use_ghe = assessment_type != 'SETOR'
        if use_ghe:
            if not ghe_id or not department_id:
                return None
            job_function_id = ''
        else:
            if not department_id or not job_function_id:
                return None
            ghe_id = ''

        cpf_hash = CampaignAccessView._hash_cpf(campaign.uuid, cpf_digits)
        if cpf_hash and CampaignResponse.all_objects.filter(campaign=campaign, cpf_hash=cpf_hash).exists():
            return None

        responses_payload = payload.get('responses') if isinstance(payload.get('responses'), dict) else {}
        return {
            'cpf_hash': cpf_hash,
            'first_name': first_name,
            'age': int(age),
            'sex': sex,
            'ghe_id': int(ghe_id) if ghe_id else None,
            'department_id': int(department_id) if department_id else None,
            'job_function_id': int(job_function_id) if job_function_id else None,
            'responses': responses_payload,
            'comments': str(payload.get('comments') or '').strip(),
        }

    def _get_session_data(self, request, campaign_uuid):
        data = request.session.get(self.SESSION_KEY, {})
        return data.get(str(campaign_uuid))

    def _store_session_data(self, request, campaign_uuid, data):
        session_data = request.session.get(self.SESSION_KEY, {})
        session_data[str(campaign_uuid)] = data
        request.session[self.SESSION_KEY] = session_data
        request.session.modified = True

    def _clear_session_data(self, request, campaign_uuid):
        session_data = request.session.get(self.SESSION_KEY, {})
        if str(campaign_uuid) in session_data:
            session_data.pop(str(campaign_uuid))
            request.session[self.SESSION_KEY] = session_data
            request.session.modified = True

    @staticmethod
    def _build_step2_context(base_context):
        questions = [
            'Diferentes setores/áreas no trabalho exigem coisas de mim que são difíceis de conciliar?',
            'Tenho prazos impossíveis de cumprir?',
            'Preciso trabalhar com muita intensidade?',
            'Preciso deixar algumas tarefas de lado porque tenho muitas demandas?',
            'Não tenho possibilidade de fazer pausas suficientes?',
            'Sofro pressão para trabalhar longas horas?',
            'Preciso trabalhar muito rápido?',
            'Tenho pausas temporárias impossíveis de cumprir?',
        ]
        return {
            **base_context,
            'section_title': 'Demandas',
            'section_description': 'Carga de trabalho, ritmos de tarefa e exigências cognitivas.',
            'questions': questions,
            'scale_options': ['Nunca', 'Raramente', 'As vezes', 'Frequentemente', 'Sempre'],
        }

    @staticmethod
    def _build_step3_context(base_context):
        questions = [
            'Posso decidir quando fazer uma pausa?',
            'Tenho voz para decidir a velocidade do meu próprio trabalho?',
            'Tenho autonomia para decidir como faço meu trabalho?',
            'Tenho autonomia para decidir o que faço no trabalho?',
            'Tenho alguma influência sobre a forma como realizo meu trabalho?',
            'Meu horário de trabalho pode ser flexível?',
        ]
        return {
            **base_context,
            'section_title': 'Controle',
            'section_description': 'Grau de autonomia do trabalhador sobre como e quando realizar suas tarefas.',
            'questions': questions,
            'scale_options': ['Nunca', 'Raramente', 'As vezes', 'Frequentemente', 'Sempre'],
        }

    @staticmethod
    def _build_step4_context(base_context):
        questions = [
            'Recebo informações e suporte que me ajudam no trabalho que eu faço?',
            'Posso contar com meu supervisor direto para me ajudar com problemas no trabalho?',
            'Posso conversar com meu supervisor direto sobre algo que me incomodou no trabalho?',
            'Recebo apoio em trabalhos emocionalmente exigentes?',
            'Meu supervisor direto me incentiva no trabalho?',
        ]
        return {
            **base_context,
            'section_title': 'Apoio da Gestao',
            'section_description': 'Suporte fornecido pela lideranca para o bem-estar do trabalhador.',
            'questions': questions,
            'scale_options': ['Nunca', 'Raramente', 'As vezes', 'Frequentemente', 'Sempre'],
        }

    @staticmethod
    def _build_step5_context(base_context):
        questions = [
            'Se o trabalho ficar difícil, meus colegas podem me ajudar?',
            'Recebo o apoio de que preciso dos meus colegas?',
            'Recebo o respeito que mereço dos meus colegas?',
            'Meus colegas estão dispostos a ouvir meus problemas relacionados ao trabalho?',
        ]
        return {
            **base_context,
            'section_title': 'Suporte dos Colegas',
            'section_description': 'Suporte organizacional entre colegas de trabalho.',
            'questions': questions,
            'scale_options': ['Nunca', 'Raramente', 'As vezes', 'Frequentemente', 'Sempre'],
        }

    @staticmethod
    def _build_step6_context(base_context):
        questions = [
            'Sou perseguido no trabalho?',
            'Há atritos ou desentendimentos entre colegas?',
            'Falam ou se comportam comigo de forma dura?',
            'Os relacionamentos no trabalho estão desgastados?',
        ]
        return {
            **base_context,
            'section_title': 'Relacionamentos',
            'section_description': 'Respeito, assédio moral, conflitos e apoio entre colegas.',
            'questions': questions,
            'scale_options': ['Nunca', 'Raramente', 'As vezes', 'Frequentemente', 'Sempre'],
        }

    @staticmethod
    def _build_step7_context(base_context):
        questions = [
            'Eu entendo claramente o que é esperado de mim no trabalho?',
            'Sei como realizar meu trabalho?',
            'Sei claramente quais são minhas funções e responsabilidades?',
            'Compreendo os objetivos e metas do meu departamento?',
            'Compreendo como o meu trabalho contribui para o objetivo geral da organização?',
        ]
        return {
            **base_context,
            'section_title': 'Clareza de Papel | Função',
            'section_description': 'Compreensão clara do papel dentro da organização.',
            'questions': questions,
            'scale_options': ['Nunca', 'Raramente', 'As vezes', 'Frequentemente', 'Sempre'],
        }

    @staticmethod
    def _build_step8_context(base_context):
        questions = [
            'Tenho oportunidades suficientes para questionar os gestores sobre mudanças no trabalho?',
            'Os funcionários são sempre consultados sobre mudanças no trabalho?',
            'Quando há mudanças no trabalho, compreendo claramente como elas serão aplicadas na prática?',
        ]
        return {
            **base_context,
            'section_title': 'Gerenciamento de Mudancas',
            'section_description': 'Como as mudancas organizacionais sao geridas e comunicadas.',
            'questions': questions,
            'scale_options': ['Nunca', 'Raramente', 'As vezes', 'Frequentemente', 'Sempre'],
        }

    @staticmethod
    def _build_step9_context(base_context):
        return {
            **base_context,
            'section_title': 'Comentários Adicionais',
            'section_description': (
                'Gostaria de compartilhar algum comentário adicional sobre sua experiência de trabalho? '
                'Este campo é opcional, mas suas observações podem ser muito valiosas para melhorar o ambiente de trabalho.'
            ),
        }

    @staticmethod
    def _build_step10_context(base_context):
        return {
            **base_context,
            'section_title': 'Finalizacao',
        }


class CampaignDepartmentsView(View):
    def get(self, request, campaign_uuid):
        campaign = get_object_or_404(
            Campaign.all_objects.select_related('company'),
            uuid=campaign_uuid,
        )
        ghe_id_raw = (request.GET.get('ghe_id') or '').strip()
        try:
            ghe_id = int(ghe_id_raw)
        except (TypeError, ValueError):
            return JsonResponse({'departments': []})

        departments = list(
            Department.all_objects.filter(
                company_id=campaign.company_id,
                is_active=True,
                ghe_id=ghe_id,
            )
            .order_by('name')
            .only('id', 'name')
        )
        return JsonResponse(
            {
                'departments': [{'id': dept.id, 'name': dept.name} for dept in departments],
            }
        )


class CampaignJobFunctionsView(View):
    def get(self, request, campaign_uuid):
        campaign = get_object_or_404(
            Campaign.all_objects.select_related('company'),
            uuid=campaign_uuid,
        )
        department_id_raw = (request.GET.get('department_id') or '').strip()
        try:
            department_id = int(department_id_raw)
        except (TypeError, ValueError):
            return JsonResponse({'job_functions': []})

        job_functions = list(
            JobFunction.all_objects.filter(
                company_id=campaign.company_id,
                is_active=True,
                departments__id=department_id,
            )
            .order_by('name')
            .only('id', 'name')
        )
        return JsonResponse(
            {
                'job_functions': [{'id': item.id, 'name': item.name} for item in job_functions],
            }
        )


class CampaignCpfCheckView(View):
    def get(self, request, campaign_uuid):
        campaign = get_object_or_404(
            Campaign.all_objects.only('uuid'),
            uuid=campaign_uuid,
        )
        cpf_raw = (request.GET.get('cpf') or '').strip()
        cpf_digits = re.sub(r'\D', '', cpf_raw)
        if len(cpf_digits) != 11:
            return JsonResponse(
                {
                    'available': False,
                    'message': 'CPF invalido.',
                }
            )

        cpf_hash = CampaignAccessView._hash_cpf(campaign.uuid, cpf_digits)
        exists = CampaignResponse.all_objects.filter(campaign=campaign, cpf_hash=cpf_hash).exists()
        return JsonResponse(
            {
                'available': not exists,
                'message': '' if not exists else 'Este CPF ja foi utilizado nesta avaliacao.',
            }
        )


class CampaignReportView(MasterRequiredMixin, View):
    template_name = 'campaigns/report.html'
    ANSWER_SCORE = {
        'Nunca': 1,
        'Raramente': 2,
        'As vezes': 3,
        'Frequentemente': 4,
        'Sempre': 5,
    }
    STEP_QUESTIONS = {
        'step2': [
            'Diferentes setores/áreas no trabalho exigem coisas de mim que são difíceis de conciliar?',
            'Tenho prazos impossíveis de cumprir?',
            'Preciso trabalhar com muita intensidade?',
            'Preciso deixar algumas tarefas de lado porque tenho muitas demandas?',
            'Não tenho possibilidade de fazer pausas suficientes?',
            'Sofro pressão para trabalhar longas horas?',
            'Preciso trabalhar muito rápido?',
            'Tenho pausas temporárias impossíveis de cumprir?',
        ],
        'step3': [
            'Posso decidir quando fazer uma pausa?',
            'Tenho voz para decidir a velocidade do meu próprio trabalho?',
            'Tenho autonomia para decidir como faço meu trabalho?',
            'Tenho autonomia para decidir o que faço no trabalho?',
            'Tenho alguma influência sobre a forma como realizo meu trabalho?',
            'Meu horário de trabalho pode ser flexível?',
        ],
        'step4': [
            'Recebo informações e suporte que me ajudam no trabalho que eu faço?',
            'Posso contar com meu supervisor direto para me ajudar com problemas no trabalho?',
            'Posso conversar com meu supervisor direto sobre algo que me incomodou no trabalho?',
            'Recebo apoio em trabalhos emocionalmente exigentes?',
            'Meu supervisor direto me incentiva no trabalho?',
        ],
        'step5': [
            'Se o trabalho ficar difícil, meus colegas podem me ajudar?',
            'Recebo o apoio de que preciso dos meus colegas?',
            'Recebo o respeito que mereço dos meus colegas?',
            'Meus colegas estão dispostos a ouvir meus problemas relacionados ao trabalho?',
        ],
        'step6': [
            'Sou perseguido no trabalho?',
            'Há atritos ou desentendimentos entre colegas?',
            'Falam ou se comportam comigo de forma dura?',
            'Os relacionamentos no trabalho estão desgastados?',
        ],
        'step7': [
            'Eu entendo claramente o que é esperado de mim no trabalho?',
            'Sei como realizar meu trabalho?',
            'Sei claramente quais são minhas funções e responsabilidades?',
            'Compreendo os objetivos e metas do meu departamento?',
            'Compreendo como o meu trabalho contribui para o objetivo geral da organização?',
        ],
        'step8': [
            'Tenho oportunidades suficientes para questionar os gestores sobre mudanças no trabalho?',
            'Os funcionários são sempre consultados sobre mudanças no trabalho?',
            'Quando há mudanças no trabalho, compreendo claramente como elas serão aplicadas na prática?',
        ],
    }
    STEP_OFFSETS = {
        'step2': 0,
        'step3': 8,
        'step4': 14,
        'step5': 19,
        'step6': 23,
        'step7': 27,
        'step8': 32,
    }
    DOMAIN_BY_STEP = {
        'step2': 'Demandas',
        'step3': 'Controle',
        'step4': 'Apoio da Gestão',
        'step5': 'Suporte dos Colegas',
        'step6': 'Relacionamentos',
        'step7': 'Clareza de Papel | Função',
        'step8': 'Gerenciamento de Mudanças',
    }

    def get(self, request, campaign_uuid):
        campaign = get_object_or_404(
            Campaign.all_objects.select_related('company'),
            uuid=campaign_uuid,
        )
        if campaign.status != Campaign.Status.FINISHED:
            messages.error(request, 'Relatório disponível apenas para campanhas encerradas.')
            return redirect('campaigns-list')
        responses_qs = CampaignResponse.all_objects.filter(campaign=campaign)
        ghe_ids = list(
            responses_qs.exclude(ghe_id__isnull=True).values_list('ghe_id', flat=True).distinct()
        )
        ghes = list(GHE.all_objects.filter(id__in=ghe_ids).order_by('name'))
        total_workers = campaign.company.employee_count or 0
        response_rate = (responses_qs.count() / total_workers * 100) if total_workers else 0
        response_label = self._response_rate_label(response_rate, total_workers)
        ghe_map = {ghe.id: ghe.name for ghe in ghes}
        standard_actions = {
            item['question_number']: item['actions']
            for item in StandardActionPlan.all_objects.filter(
                company_id=campaign.company_id,
                is_active=True,
            ).values('question_number', 'actions')
        }
        results = self._build_results(responses_qs, ghe_map, standard_actions)
        saved_actions = CampaignReportAction.all_objects.filter(campaign=campaign).values(
            'question_text',
            'measures',
            'implantation_months',
            'status',
            'concluded_on',
        )
        report_settings = CampaignReportSettings.all_objects.filter(campaign=campaign).first()
        context = {
            'campaign': campaign,
            'company': campaign.company,
            'is_master': True,
            'active_menu': 'campaigns',
            'responses_count': responses_qs.count(),
            'total_workers': total_workers,
            'response_rate': round(response_rate, 1) if total_workers else 0,
            'response_label': response_label,
            'report_ghes': ghes,
            'results': results,
            'report_actions_json': json.dumps(list(saved_actions), ensure_ascii=False),
            'report_settings': report_settings,
            'report_attachments_json': json.dumps(
                (report_settings.attachments if report_settings else []),
                ensure_ascii=False,
            ),
        }
        return render(request, self.template_name, context)


    def _build_results(self, responses_qs, ghe_map, standard_actions):
        domain_totals = {key: {'sum': 0, 'count': 0} for key in self.DOMAIN_BY_STEP.keys()}
        question_totals = {
            key: [{'sum': 0, 'count': 0} for _ in self.STEP_QUESTIONS.get(key, [])]
            for key in self.DOMAIN_BY_STEP.keys()
        }
        ghe_totals = {key: {} for key in self.DOMAIN_BY_STEP.keys()}
        ghe_question_totals = {
            key: {} for key in self.DOMAIN_BY_STEP.keys()
        }
        overall_sum = 0
        overall_count = 0

        for response in responses_qs:
            answers_by_step = response.responses or {}
            ghe_id = response.ghe_id
            for step_key, answers in answers_by_step.items():
                if step_key not in self.DOMAIN_BY_STEP or not answers:
                    continue
                for idx, item in enumerate(answers):
                    score = self.ANSWER_SCORE.get(item.get('answer', ''))
                    if not score:
                        continue
                    domain_totals[step_key]['sum'] += score
                    domain_totals[step_key]['count'] += 1
                    overall_sum += score
                    overall_count += 1
                    if idx < len(question_totals[step_key]):
                        question_totals[step_key][idx]['sum'] += score
                        question_totals[step_key][idx]['count'] += 1
                    if ghe_id:
                        ghe_totals[step_key].setdefault(ghe_id, {'sum': 0, 'count': 0})
                        ghe_totals[step_key][ghe_id]['sum'] += score
                        ghe_totals[step_key][ghe_id]['count'] += 1
                        ghe_question_totals[step_key].setdefault(
                            ghe_id,
                            [{'sum': 0, 'count': 0} for _ in self.STEP_QUESTIONS.get(step_key, [])],
                        )
                        if idx < len(ghe_question_totals[step_key][ghe_id]):
                            ghe_question_totals[step_key][ghe_id][idx]['sum'] += score
                            ghe_question_totals[step_key][ghe_id][idx]['count'] += 1

        domains = []
        domain_details = []
        for step_key, label in self.DOMAIN_BY_STEP.items():
            count = domain_totals[step_key]['count']
            avg = (domain_totals[step_key]['sum'] / count) if count else 0
            percent = (avg / 5) * 100 if count else 0
            domains.append(
                {
                    'label': label,
                    'avg': round(avg, 1) if count else 0,
                    'percent': round(percent, 1) if count else 0,
                    'percent_css': f'{percent:.1f}',
                }
            )
            ghe_items = []
            ghe_question_items = []
            for ghe_id, totals in ghe_totals[step_key].items():
                ghe_avg = (totals['sum'] / totals['count']) if totals['count'] else 0
                ghe_percent = (ghe_avg / 5) * 100 if totals['count'] else 0
                ghe_items.append(
                    {
                        'name': ghe_map.get(ghe_id, f'GHE {ghe_id}'),
                        'avg': round(ghe_avg, 1) if totals['count'] else 0,
                        'percent': round(ghe_percent, 1) if totals['count'] else 0,
                        'percent_css': f'{ghe_percent:.1f}',
                    }
                )
                ghe_questions = []
                for idx, question in enumerate(self.STEP_QUESTIONS.get(step_key, [])):
                    question_number = self.STEP_OFFSETS.get(step_key, 0) + idx + 1
                    q_count = ghe_question_totals[step_key][ghe_id][idx]['count']
                    q_avg = (
                        ghe_question_totals[step_key][ghe_id][idx]['sum'] / q_count
                        if q_count
                        else 0
                    )
                    q_percent = (q_avg / 5) * 100 if q_count else 0
                    ghe_questions.append(
                        {
                            'text': question,
                            'question_number': question_number,
                            'avg_raw': q_avg,
                            'avg': round(q_avg, 1) if q_count else 0,
                            'percent': round(q_percent, 1) if q_count else 0,
                            'percent_css': f'{q_percent:.1f}',
                            'zone': self._zone_label(q_percent) if q_count else 'Sem dados',
                            'actions': standard_actions.get(question_number, []),
                        }
                    )
                ghe_question_items.append(
                    {
                        'name': ghe_map.get(ghe_id, f'GHE {ghe_id}'),
                        'questions': ghe_questions,
                    }
                )
            questions = []
            for idx, question in enumerate(self.STEP_QUESTIONS.get(step_key, [])):
                question_number = self.STEP_OFFSETS.get(step_key, 0) + idx + 1
                q_count = question_totals[step_key][idx]['count']
                q_avg = (
                    question_totals[step_key][idx]['sum'] / q_count
                    if q_count
                    else 0
                )
                q_percent = (q_avg / 5) * 100 if q_count else 0
                questions.append(
                    {
                        'text': question,
                        'question_number': question_number,
                        'avg_raw': q_avg,
                        'avg': round(q_avg, 1) if q_count else 0,
                        'percent': round(q_percent, 1) if q_count else 0,
                        'percent_css': f'{q_percent:.1f}',
                        'zone': self._zone_label(q_percent) if q_count else 'Sem dados',
                        'actions': standard_actions.get(question_number, []),
                    }
                )
            domain_details.append(
                {
                    'label': label,
                    'avg': round(avg, 1) if count else 0,
                    'percent': round(percent, 1) if count else 0,
                    'percent_css': f'{percent:.1f}',
                    'ghes': sorted(ghe_items, key=lambda item: item['name']),
                    'questions': questions,
                    'ghe_questions': sorted(ghe_question_items, key=lambda item: item['name']),
                }
            )

        overall_avg = (overall_sum / overall_count) if overall_count else 0
        overall_percent = (overall_avg / 5) * 100 if overall_count else 0
        overall_label = self._score_label(overall_avg) if overall_count else 'Sem dados'

        return {
            'overall_avg': round(overall_avg, 1) if overall_count else 0,
            'overall_percent': round(overall_percent, 1) if overall_count else 0,
            'overall_label': overall_label,
            'domains': domains,
            'domain_details': domain_details,
        }

    @staticmethod
    def _score_label(avg):
        if avg >= 4:
            return 'Adequado'
        if avg >= 3:
            return 'Moderado'
        return 'Critico'

    @staticmethod
    def _zone_label(percent):
        if percent >= 75:
            return 'BOM'
        if percent >= 40:
            return 'ATENÇÃO'
        return 'RUIM'

    @staticmethod
    def _response_rate_label(rate, total_workers):
        if not total_workers:
            return 'Sem dados'
        if rate >= 75:
            return 'Bom'
        if rate >= 40:
            return 'Atenção'
        return 'Critico'


class CampaignReportSaveView(MasterRequiredMixin, View):
    def post(self, request, campaign_uuid):
        campaign = get_object_or_404(
            Campaign.all_objects.select_related('company'),
            uuid=campaign_uuid,
        )
        payload = None
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            raw_payload = request.POST.get('payload', '')
            try:
                payload = json.loads(raw_payload) if raw_payload else None
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Payload invalido.'}, status=400)
        else:
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Payload invalido.'}, status=400)

        if not payload:
            return JsonResponse({'error': 'Payload invalido.'}, status=400)

        items = payload.get('items', [])
        reevaluate_months = payload.get('reevaluate_months')
        attachments = payload.get('attachments', [])
        if not isinstance(items, list):
            return JsonResponse({'error': 'Formato invalido.'}, status=400)

        saved = 0
        normalized_items = []
        for item in items:
            question_text = (item.get('question_text') or '').strip()
            if not question_text:
                continue
            normalized_items.append(
                {
                    'question_text': question_text,
                    'measures': item.get('measures') or [],
                    'months': item.get('implantation_months') or [],
                    'status': item.get('status') or {},
                    'concluded_on': (item.get('concluded_on') or '').strip(),
                }
            )

        if normalized_items:
            question_texts = [item['question_text'] for item in normalized_items]
            existing_actions = {
                action.question_text: action
                for action in CampaignReportAction.all_objects.filter(
                    campaign=campaign,
                    question_text__in=question_texts,
                )
            }

            to_create = []
            to_update = []
            for item in normalized_items:
                action = existing_actions.get(item['question_text'])
                if action:
                    action.measures = item['measures']
                    action.implantation_months = item['months']
                    action.status = item['status']
                    action.concluded_on = item['concluded_on']
                    to_update.append(action)
                else:
                    to_create.append(
                        CampaignReportAction(
                            campaign=campaign,
                            company=campaign.company,
                            question_text=item['question_text'],
                            measures=item['measures'],
                            implantation_months=item['months'],
                            status=item['status'],
                            concluded_on=item['concluded_on'],
                        )
                    )

            if to_create:
                CampaignReportAction.all_objects.bulk_create(to_create, batch_size=200)
            if to_update:
                CampaignReportAction.all_objects.bulk_update(
                    to_update,
                    ['measures', 'implantation_months', 'status', 'concluded_on'],
                    batch_size=200,
                )

            saved = len(normalized_items)

        updated_attachments = []
        if isinstance(attachments, list):
            for idx, attachment in enumerate(attachments):
                if not isinstance(attachment, dict):
                    continue
                file_index = attachment.get('file_index')
                uploaded_file = None
                if file_index is not None:
                    uploaded_file = request.FILES.get(f'attachments_file_{file_index}')
                stored_path = (attachment.get('stored_path') or '').strip()
                if stored_path:
                    if '://' in stored_path:
                        stored_path = urlparse(stored_path).path
                    stored_path = stored_path.lstrip('/')
                stored_name = (attachment.get('stored_name') or '').strip()
                original_name = (attachment.get('original_name') or '').strip()
                title = (attachment.get('title') or '').strip()
                description = (attachment.get('description') or '').strip()

                if uploaded_file:
                    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                    original_name = uploaded_file.name
                    base_name = Path(original_name).stem
                    extension = Path(original_name).suffix.lower()
                    safe_base = slugify(base_name) or uuid4().hex
                    safe_base = safe_base.strip('-_')[:80] or uuid4().hex
                    safe_name = f"{safe_base}{extension}"
                    stored_name = f"{timestamp}_{safe_name}"[:180]
                    stored_path = f"report_attachments/{campaign.uuid}/{stored_name}"
                    if not title:
                        title = f"{timestamp}_{safe_name}"
                    print(f"[report] saving attachment key: {stored_path} (len={len(stored_path)})")
                    default_storage.save(stored_path, uploaded_file)

                if title or description or stored_path or original_name:
                    updated_attachments.append(
                        {
                            'title': title,
                            'description': description,
                            'stored_path': stored_path,
                            'stored_name': stored_name,
                            'original_name': original_name,
                        }
                    )

        if isinstance(reevaluate_months, int) or isinstance(attachments, list):
            CampaignReportSettings.all_objects.update_or_create(
                campaign=campaign,
                defaults={
                    'company': campaign.company,
                    'reevaluate_months': reevaluate_months if isinstance(reevaluate_months, int) else 3,
                    'attachments': updated_attachments if isinstance(attachments, list) else [],
                },
            )

        return JsonResponse({'saved': saved})


class CampaignReportPdfView(MasterRequiredMixin, View):
    def get(self, request, campaign_uuid):
        campaign = get_object_or_404(
            Campaign.all_objects.select_related('company'),
            uuid=campaign_uuid,
        )
        if campaign.status != Campaign.Status.FINISHED:
            messages.error(request, 'Relatorio disponivel apenas para campanhas encerradas.')
            return redirect('campaigns-list')

        company = campaign.company
        address_parts = []
        if company.address_street:
            address_parts.append(company.address_street)
        if company.address_number:
            address_parts.append(company.address_number)
        if company.address_complement:
            address_parts.append(company.address_complement)
        if company.address_neighborhood:
            address_parts.append(company.address_neighborhood)
        city_state = ''
        if company.address_city:
            city_state = company.address_city
        if company.address_state:
            city_state = f'{city_state}/{company.address_state}' if city_state else company.address_state
        if city_state:
            address_parts.append(city_state)
        if company.address_zipcode:
            address_parts.append(f'CEP: {company.address_zipcode}')
        company_address = ' - '.join(address_parts) if address_parts else '-'

        responses_qs = CampaignResponse.all_objects.filter(campaign=campaign)
        ghe_ids = list(
            responses_qs.exclude(ghe_id__isnull=True).values_list('ghe_id', flat=True).distinct()
        )
        ghes = list(GHE.all_objects.filter(id__in=ghe_ids).order_by('name'))
        ghes_label = ', '.join([ghe.name for ghe in ghes]) if ghes else '-'
        evaluation_date = campaign.end_date.strftime('%d/%m/%Y') if campaign.end_date else '-'
        total_workers = company.employee_count or 0
        response_rate = (responses_qs.count() / total_workers * 100) if total_workers else 0
        response_label = CampaignReportView._response_rate_label(response_rate, total_workers)
        ghe_map = {ghe.id: ghe.name for ghe in ghes}
        standard_actions = {
            item['question_number']: item['actions']
            for item in StandardActionPlan.all_objects.filter(
                company_id=campaign.company_id,
                is_active=True,
            ).values('question_number', 'actions')
        }
        results = CampaignReportView()._build_results(responses_qs, ghe_map, standard_actions)
        technical_responsibles_qs = TechnicalResponsible.objects.filter(
            is_active=True,
        ).order_by('sort_order', 'name')

        report_context = {
            'campaign_uuid': str(campaign.uuid),
            'company_name': company.name or '-',
            'company_cnpj': company.cnpj or '-',
            'company_address': company_address,
            'company_cnae': company.cnae or '-',
            'company_risk': f"Grau {company.risk_level}" if company.risk_level else '-',
            'company_ghes': ghes_label,
            'responses_count': responses_qs.count(),
            'evaluation_date': evaluation_date,
            'total_workers': total_workers,
            'response_rate': round(response_rate, 1) if total_workers else 0,
            'response_label': response_label,
            'results': results,
            'company_legal_representative_name': company.legal_representative_name or '-',
            'company_legal_representative_company': company.legal_name or company.name or '-',
            'evaluation_representative_name': ensure_master_report_settings().evaluation_representative_name or '-',
            'evaluation_representative_location': ensure_master_report_settings().evaluation_representative_location or '-',
            'evaluation_company_name': 'CISS CONSULTORIA',
              'technical_responsibles': list(
                  technical_responsibles_qs.values('name', 'education', 'registration')
              ),
        'report_actions': list(
            CampaignReportAction.all_objects.filter(campaign=campaign).values(
                'question_text',
                'measures',
                'implantation_months',
                'status',
                'concluded_on',
            )
        ),
    'reevaluate_months': (
        CampaignReportSettings.all_objects.filter(campaign=campaign).values_list('reevaluate_months', flat=True).first()
        or 3
    ),
    'attachments': (
        CampaignReportSettings.all_objects.filter(campaign=campaign).values_list('attachments', flat=True).first()
        or []
    ),
}
        pdf_bytes = build_campaign_report_pdf(report_context)
        filename = f"relatorio-campanha-{campaign.uuid}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


def build_period():
    today = date.today()
    return today, today.replace(day=1), today


DEFAULT_MOOD_TYPE_SEED = [
    ('Muito bem', '😀', 'very_good', 5),
    ('Bem', '🙂', 'good', 4),
    ('Mais ou menos', '😐', 'neutral', 3),
    ('Normal', '😌', 'neutral', 3),
    ('Triste', '😟', 'bad', 2),
    ('Irritado', '😠', 'very_bad', 1),
    ('Sobrecarregado', '😩', 'bad', 2),
    ('Cansado', '😪', 'bad', 2),
    ('Desmotivado', '😞', 'bad', 2),
    ('Desapontado', '🙁', 'bad', 2),
    ('Estressado', '😣', 'very_bad', 1),
]
DEFAULT_COMPLAINT_TYPE_SEED = [
    'Assedio moral',
    'Assedio sexual',
    'Discriminacao',
    'Conduta antietica',
    'Violencia psicologica',
]


def ensure_default_totem_types(company):
    existing_mood_labels = set(
        MoodType.all_objects.filter(company=company).values_list('label', flat=True)
    )
    mood_to_create = [
        MoodType(
            company=company,
            label=label,
            emoji=emoji,
            sentiment=sentiment,
            mood_score=score,
            is_active=True,
        )
        for label, emoji, sentiment, score in DEFAULT_MOOD_TYPE_SEED
        if label not in existing_mood_labels
    ]
    if mood_to_create:
        MoodType.all_objects.bulk_create(mood_to_create)

    existing_complaint_labels = set(
        ComplaintType.all_objects.filter(company=company).values_list('label', flat=True)
    )
    complaint_to_create = [
        ComplaintType(
            company=company,
            label=label,
            is_active=True,
        )
        for label in DEFAULT_COMPLAINT_TYPE_SEED
        if label not in existing_complaint_labels
    ]
    if complaint_to_create:
        ComplaintType.all_objects.bulk_create(complaint_to_create)


def ensure_alert_settings(company):
    return AlertSetting.all_objects.get_or_create(
        company=company,
        defaults={
            'auto_alerts_enabled': True,
            'analysis_window_days': 30,
            'max_critical_complaints': 5,
            'max_negative_mood_percent': 35,
            'max_open_help_requests': 10,
            'is_active': True,
        },
    )[0]


def ensure_master_report_settings():
    return MasterReportSettings.objects.get_or_create(
        defaults={
            'evaluation_representative_name': '',
            'evaluation_representative_location': '',
        },
    )[0]


def _notify_alert_recipients(company_id, subject, body):
    recipients = list(
        AlertRecipient.all_objects.filter(
            company_id=company_id,
            is_active=True,
        ).values_list('email', flat=True)
    )
    if not recipients:
        return
    send_mail(
        subject,
        body,
        None,
        recipients,
        fail_silently=True,
    )


def _create_automatic_alert_if_missing(company_id, alert_type, level, period_start, period_end, message):
    today = date.today()
    already_exists = Alert.all_objects.filter(
        company_id=company_id,
        alert_type=alert_type,
        record_date=today,
        status='open',
    ).exists()
    if already_exists:
        return

    Alert.all_objects.create(
        company_id=company_id,
        alert_type=alert_type,
        level=level,
        status='open',
        record_date=today,
        period_start=period_start,
        period_end=period_end,
    )
    _notify_alert_recipients(
        company_id,
        f'Alerta automático: {alert_type}',
        message,
    )


def evaluate_automatic_alerts(company):
    settings_obj = ensure_alert_settings(company)
    if not settings_obj.is_active or not settings_obj.auto_alerts_enabled:
        return

    today = date.today()
    days = max(int(settings_obj.analysis_window_days or 30), 1)
    period_start = today - timedelta(days=days - 1)
    period_end = today

    complaint_count = Complaint.all_objects.filter(
        company=company,
        record_date__gte=period_start,
        record_date__lte=period_end,
    ).count()
    if complaint_count >= settings_obj.max_critical_complaints:
        level = 'critical' if complaint_count >= (settings_obj.max_critical_complaints * 1.5) else 'high'
        _create_automatic_alert_if_missing(
            company.id,
            'complaint',
            level,
            period_start,
            period_end,
            (
                f'Foram registradas {complaint_count} denuncias nos ultimos {days} dias. '
                f'Limite configurado: {settings_obj.max_critical_complaints}.'
            ),
        )

    mood_qs = MoodRecord.all_objects.filter(
        company=company,
        record_date__gte=period_start,
        record_date__lte=period_end,
    )
    mood_total = mood_qs.count()
    if mood_total > 0:
        negative_total = mood_qs.filter(sentiment__in=['bad', 'very_bad']).count()
        negative_percent = (negative_total * 100) / mood_total
        if negative_percent >= float(settings_obj.max_negative_mood_percent):
            level = 'critical' if negative_percent >= float(settings_obj.max_negative_mood_percent) + 10 else 'high'
            _create_automatic_alert_if_missing(
                company.id,
                'risk',
                level,
                period_start,
                period_end,
                (
                    f'O percentual de humor negativo esta em {negative_percent:.1f}% nos últimos {days} dias. '
                    f'Limite configurado: {settings_obj.max_negative_mood_percent}%.'
                ),
            )

    open_help_requests = HelpRequest.all_objects.filter(
        company=company,
        status__in=[HelpRequest.Status.OPEN, HelpRequest.Status.IN_PROGRESS],
    ).count()
    if open_help_requests >= settings_obj.max_open_help_requests:
        level = 'critical' if open_help_requests >= (settings_obj.max_open_help_requests * 1.5) else 'high'
        _create_automatic_alert_if_missing(
            company.id,
            'operational',
            level,
            period_start,
            period_end,
            (
                f'Existem {open_help_requests} pedidos de ajuda em aberto/em atendimento. '
                f'Limite configurado: {settings_obj.max_open_help_requests}.'
            ),
        )


class TotemView(View):
    template_name = 'totem/index.html'

    def get(self, request, company_slug, totem_slug):
        company = get_object_or_404(Company, slug=company_slug, is_active=True)
        ensure_default_totem_types(company)
        totem = get_object_or_404(
            Totem.all_objects,
            company=company,
            slug=totem_slug,
            is_active=True,
        )
        return render(
            request,
            self.template_name,
            {
                'company': company,
                'totem': totem,
                'departments': Department.all_objects.filter(
                    company=company,
                    is_active=True,
                ).order_by('name'),
                'mood_options': MoodType.all_objects.filter(
                    company=company,
                    is_active=True,
                ).order_by('label'),
                'complaint_options': ComplaintType.all_objects.filter(
                    company=company,
                    is_active=True,
                ).order_by('label'),
            },
        )


class TotemMoodSubmitView(View):
    def post(self, request, company_slug, totem_slug):
        company = get_object_or_404(Company, slug=company_slug, is_active=True)
        ensure_default_totem_types(company)
        totem = get_object_or_404(
            Totem.all_objects,
            company=company,
            slug=totem_slug,
            is_active=True,
        )
        raw_mood_type_id = (request.POST.get('mood_option') or '').strip()
        try:
            mood_type_id = int(raw_mood_type_id)
        except (TypeError, ValueError):
            mood_type_id = None
        mood_type = MoodType.all_objects.filter(
            company=company,
            id=mood_type_id,
            is_active=True,
        ).first()
        if mood_type is None:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'message': 'Nao foi possivel registrar o humor.'}, status=400)
            messages.error(request, 'Nao foi possivel registrar o humor.')
            return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)
        raw_department_id = (request.POST.get('department_id') or '').strip()
        try:
            department_id = int(raw_department_id)
        except (TypeError, ValueError):
            department_id = None

        department = None
        if department_id:
            department = Department.all_objects.filter(
                id=department_id,
                company=company,
                is_active=True,
            ).first()
        if department is None:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'message': 'Selecione um setor valido para registrar o humor.'}, status=400)
            messages.error(request, 'Selecione um setor valido para registrar o humor.')
            return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)

        record_date, period_start, period_end = build_period()
        MoodRecord.all_objects.create(
            company=company,
            totem=totem,
            department=department,
            sentiment=mood_type.sentiment,
            mood_score=mood_type.mood_score,
            record_date=record_date,
            period_start=period_start,
            period_end=period_end,
            channel='totem',
        )
        cache.clear()
        evaluate_automatic_alerts(company)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'message': 'Humor registrado com sucesso.'})
        messages.success(request, 'Humor registrado com sucesso.')
        return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)

class TotemComplaintSubmitView(View):
    def post(self, request, company_slug, totem_slug):
        company = get_object_or_404(Company, slug=company_slug, is_active=True)
        ensure_default_totem_types(company)
        totem = get_object_or_404(
            Totem.all_objects,
            company=company,
            slug=totem_slug,
            is_active=True,
        )
        raw_complaint_type_id = (request.POST.get('complaint_category') or '').strip()
        try:
            complaint_type_id = int(raw_complaint_type_id)
        except (TypeError, ValueError):
            complaint_type_id = None
        details = (request.POST.get('details') or '').strip()
        complaint_department_name = (request.POST.get('complaint_department_name') or '').strip()
        complaint_additional_details = (request.POST.get('complaint_additional_details') or '').strip()

        complaint_type = ComplaintType.all_objects.filter(
            company=company,
            id=complaint_type_id,
            is_active=True,
        ).first()
        if complaint_type is None:
            messages.error(request, 'Nao foi possivel registrar a denuncia.')
            return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)
        if not complaint_department_name or not complaint_additional_details:
            messages.error(request, 'Informe setor e detalhes do ocorrido para concluir a denuncia.')
            return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)
        details_parts = [
            f'Setor: {complaint_department_name}',
            f'Relato: {complaint_additional_details}',
        ]
        if details:
            details_parts.append(f'Complemento: {details}')
        details = ' | '.join(details_parts)

        record_date, period_start, period_end = build_period()
        complaint = Complaint.all_objects.create(
            company=company,
            totem=totem,
            category=complaint_type.label[:40].lower().replace(' ', '_'),
            complaint_status='RECEIVED',
            occurrence_count=1,
            record_date=record_date,
            period_start=period_start,
            period_end=period_end,
            channel='totem',
            details=details,
        )
        ComplaintActionHistory.all_objects.create(
            company=company,
            complaint=complaint,
            complaint_status='RECEIVED',
            action_note='Denuncia recebida via totem.',
        )
        cache.clear()
        evaluate_automatic_alerts(company)
        messages.success(request, 'Denuncia registrada com sucesso.')
        return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)


class TotemHelpRequestSubmitView(View):
    def post(self, request, company_slug, totem_slug):
        company = get_object_or_404(Company, slug=company_slug, is_active=True)
        totem = get_object_or_404(
            Totem.all_objects,
            company=company,
            slug=totem_slug,
            is_active=True,
        )

        requester_name = (request.POST.get('requester_name') or '').strip()
        department_name = (request.POST.get('department_name') or '').strip()

        if not requester_name or not department_name:
            messages.error(request, 'Informe nome e setor para solicitar ajuda.')
            return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)

        HelpRequest.all_objects.create(
            company=company,
            totem=totem,
            requester_name=requester_name,
            department_name=department_name,
            status=HelpRequest.Status.OPEN,
        )
        cache.clear()
        evaluate_automatic_alerts(company)
        messages.success(request, 'Pedido de ajuda registrado. Nossa equipe vai ate voce.')
        return redirect('totem-home', company_slug=company.slug, totem_slug=totem.slug)


class CompanyAdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            company_id = request.session.get('company_id')
            if not company_id:
                return redirect('company-select')
            try:
                company_id = int(company_id)
            except (TypeError, ValueError) as exc:
                raise PermissionDenied('Empresa de sessao invalida.') from exc
            request.current_company_id = company_id
            request.current_membership = None
            return super().dispatch(request, *args, **kwargs)
        company_id = request.session.get('company_id')
        if not company_id:
            return redirect('company-select')

        try:
            company_id = int(company_id)
        except (TypeError, ValueError) as exc:
            raise PermissionDenied('Empresa de sessao invalida.') from exc

        membership = get_membership_for_company(request.user, company_id)
        if membership is None:
            raise PermissionDenied('Usuario sem acesso a empresa da sessao.')
        if membership.role not in CompanyMembership.ADMIN_ROLES:
            raise PermissionDenied('Apenas ADMIN_EMPRESA pode gerenciar acessos.')

        request.current_company_id = company_id
        request.current_membership = membership
        return super().dispatch(request, *args, **kwargs)


class TotemForm(forms.Form):
    name = forms.CharField(max_length=150)
    location = forms.CharField(max_length=180, required=False)


MAX_COMPANY_LOGO_SIZE = 2 * 1024 * 1024


class CompanyForm(forms.Form):
    document_type = forms.ChoiceField(
        choices=(('cnpj', 'CNPJ'), ('cpf', 'CPF')),
        required=False,
    )
    unit_type = forms.ChoiceField(
        choices=(('matriz', 'Matriz'), ('filial', 'Filial'), ('unidade', 'Unidade'), ('outro', 'Outro')),
        required=False,
    )
    unit_name = forms.CharField(max_length=255, required=False)
    name = forms.CharField(max_length=255)
    legal_name = forms.CharField(max_length=255, required=False)
    legal_representative_name = forms.CharField(max_length=255)
    responsible_email = forms.EmailField(max_length=255, required=False)
    cnpj = forms.CharField(max_length=18)
    assessment_type = forms.ChoiceField(choices=(('setor', 'Setor'), ('ghe', 'GHE')), required=False)
    cnae = forms.CharField(max_length=20, required=False)
    risk_level = forms.IntegerField(min_value=1, max_value=4, required=False)
    employee_count = forms.IntegerField(min_value=0, required=False)
    max_users = forms.IntegerField(min_value=0, required=False)
    max_totems = forms.IntegerField(min_value=0, required=False)
    address_street = forms.CharField(max_length=255, required=False)
    address_number = forms.CharField(max_length=40, required=False)
    address_complement = forms.CharField(max_length=120, required=False)
    address_neighborhood = forms.CharField(max_length=120, required=False)
    address_city = forms.CharField(max_length=120, required=False)
    address_state = forms.CharField(max_length=2, required=False)
    address_zipcode = forms.CharField(max_length=10, required=False)
    logo = forms.ImageField(required=False)
    is_active = forms.BooleanField(required=False, initial=True)

    def clean_cnpj(self):
        raw = (self.cleaned_data.get('cnpj') or '').strip()
        digits = re.sub(r'\D', '', raw)
        document_type = (self.cleaned_data.get('document_type') or self.data.get('document_type') or 'cnpj').lower()
        if document_type == 'cpf':
            if len(digits) != 11:
                raise forms.ValidationError('CPF deve conter 11 digitos numericos.')
        else:
            if len(digits) != 14:
                raise forms.ValidationError('CNPJ deve conter 14 digitos numericos.')
        return digits

    def clean_employee_count(self):
        value = self.cleaned_data.get('employee_count')
        if value is None:
            return 0
        return value

    def clean_max_users(self):
        value = self.cleaned_data.get('max_users')
        if value is None:
            return 0
        return value

    def clean_max_totems(self):
        value = self.cleaned_data.get('max_totems')
        if value is None:
            return 0
        return value

    def clean_address_state(self):
        value = (self.cleaned_data.get('address_state') or '').strip().upper()
        if value and len(value) != 2:
            raise forms.ValidationError('UF deve conter 2 letras.')
        return value

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')
        if not logo:
            return logo
        if logo.size > MAX_COMPANY_LOGO_SIZE:
            max_mb = MAX_COMPANY_LOGO_SIZE // (1024 * 1024)
            raise forms.ValidationError(
                f'Logo deve ter no maximo {max_mb}MB.'
            )
        return logo


class DepartmentForm(forms.Form):
    name = forms.CharField(max_length=150)
    ghe_id = forms.IntegerField()
    is_active = forms.BooleanField(required=False, initial=True)


class JobFunctionForm(forms.Form):
    name = forms.CharField(max_length=150)
    ghes = forms.MultipleChoiceField(required=False)
    departments = forms.MultipleChoiceField(required=False)
    is_active = forms.BooleanField(required=False, initial=True)


class GHEForm(forms.Form):
    name = forms.CharField(max_length=150)
    is_active = forms.BooleanField(required=False, initial=True)


class CampaignForm(forms.Form):
    title = forms.CharField(max_length=255)
    company_id = forms.IntegerField()
    start_date = forms.DateField()
    end_date = forms.DateField()
    status = forms.ChoiceField(choices=Campaign.Status.choices)

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get('start_date')
        end_date = cleaned.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('Data final deve ser maior ou igual a data inicial.')
        return cleaned


class MoodTypeForm(forms.Form):
    EMOJI_SUGGESTIONS = ['😀', '🙂', '😌', '😐', '🙁', '😟', '😣', '😠', '😩', '😪']
    SENTIMENT_CHOICES = [
        ('very_good', 'Muito bem'),
        ('good', 'Bem'),
        ('neutral', 'Neutro'),
        ('bad', 'Triste/Cansado'),
        ('very_bad', 'Irritado/Estressado'),
    ]

    label = forms.CharField(max_length=80)
    emoji = forms.CharField(max_length=32, initial='🙂')
    sentiment = forms.ChoiceField(choices=SENTIMENT_CHOICES)
    mood_score = forms.IntegerField(min_value=1, max_value=5)

    def clean_emoji(self):
        emoji = (self.cleaned_data.get('emoji') or '').strip()
        if not emoji:
            raise forms.ValidationError('Emoji e obrigatorio.')
        return emoji


class ComplaintTypeForm(forms.Form):
    label = forms.CharField(max_length=80)


class MasterReportSettingsForm(forms.Form):
    evaluation_representative_name = forms.CharField(max_length=255, required=True)
    evaluation_representative_location = forms.CharField(max_length=255, required=False)


class TechnicalResponsibleForm(forms.Form):
    name = forms.CharField(max_length=150)
    education = forms.CharField(max_length=255)
    registration = forms.CharField(max_length=80)
    sort_order = forms.IntegerField(min_value=0, required=False)
    is_active = forms.BooleanField(required=False, initial=True)


class AlertSettingForm(forms.Form):
    auto_alerts_enabled = forms.BooleanField(required=False, initial=True)
    is_active = forms.BooleanField(required=False, initial=True)
    analysis_window_days = forms.IntegerField(min_value=1, max_value=365)
    max_critical_complaints = forms.IntegerField(min_value=1, max_value=100000)
    max_negative_mood_percent = forms.DecimalField(min_value=0, max_value=100, decimal_places=2, max_digits=5)
    max_open_help_requests = forms.IntegerField(min_value=1, max_value=100000)


class AlertRecipientForm(forms.Form):
    name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(max_length=254)
    is_active = forms.BooleanField(required=False, initial=True)


class ReportGenerateForm(forms.Form):
    report_template = forms.ChoiceField(choices=Report.REPORT_TEMPLATE_CHOICES)
    report_type = forms.ChoiceField(choices=Report.REPORT_TYPE_CHOICES)
    title = forms.CharField(max_length=255, required=False)
    period_start = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    period_end = forms.DateField(required=False, input_formats=['%Y-%m-%d'])

    def clean(self):
        cleaned_data = super().clean()
        period_start = cleaned_data.get('period_start')
        period_end = cleaned_data.get('period_end')
        if period_start and period_end and period_start > period_end:
            raise forms.ValidationError('Periodo inicial nao pode ser maior que o periodo final.')
        return cleaned_data


class ComplaintUpdateForm(forms.Form):
    complaint_status = forms.ChoiceField(choices=Complaint.STATUS_CHOICES)
    action_note = forms.CharField(required=True, widget=forms.Textarea)


class HelpRequestUpdateForm(forms.Form):
    status = forms.ChoiceField(choices=HelpRequest.Status.choices)
    admin_notes = forms.CharField(required=False, widget=forms.Textarea)


class InternalUserBaseForm(forms.Form):
    ROLE_CHOICES = [
        (CompanyMembership.Role.ADMIN_EMPRESA, 'Admin Empresa'),
        (CompanyMembership.Role.GESTOR, 'Gestor'),
        (CompanyMembership.Role.RH, 'RH'),
        (CompanyMembership.Role.COLABORADOR, 'Colaborador'),
    ]

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    is_active = forms.BooleanField(required=False, initial=True)


class InternalUserCreateForm(InternalUserBaseForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)


class InternalUserUpdateForm(InternalUserBaseForm):
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, required=False)


def collect_form_errors(form):
    errors = []
    for field_name, field_errors in form.errors.items():
        label = form.fields.get(field_name).label if field_name in form.fields else field_name
        for error in field_errors:
            errors.append(f'{label}: {error}')
    return ' | '.join(errors) if errors else 'Dados invalidos.'


def build_pagination_query(request):
    params = request.GET.copy()
    params.pop('page', None)
    params.pop('partial', None)
    return params.urlencode()


def paginate_queryset(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get('page') or 1)


class TotemListView(CompanyAdminRequiredMixin, View):
    template_name = 'totems/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        totems_qs = Totem.all_objects.filter(company_id=request.current_company_id).order_by('name')
        page_obj = paginate_queryset(request, totems_qs)
        context = {
            'totems': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'totems',
            'can_manage_access': True,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'totems/_table_container.html', context)
        return render(request, self.template_name, context)


class TotemCreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = TotemForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            return redirect('totems-list')

        company = get_object_or_404(Company, pk=request.current_company_id)
        if company.max_totems:
            active_totems = Totem.all_objects.filter(
                company_id=request.current_company_id,
                is_active=True,
            ).count()
            if active_totems >= company.max_totems:
                messages.error(request, 'Limite de totens atingido para esta empresa.')
                return redirect('totems-list')

        final_slug = uuid4().hex[:12]
        while Totem.all_objects.filter(
            company_id=request.current_company_id,
            slug=final_slug,
        ).exists():
            final_slug = uuid4().hex[:12]

        Totem.all_objects.create(
            company_id=request.current_company_id,
            name=form.cleaned_data['name'],
            slug=final_slug,
            location=form.cleaned_data['location'],
        )
        cache.clear()
        messages.success(request, 'Totem criado com sucesso.')
        if is_ajax_request(request):
            return render_totems_table(request)
        return redirect('totems-list')


class TotemUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, totem_id):
        totem = get_object_or_404(
            Totem.all_objects,
            pk=totem_id,
            company_id=request.current_company_id,
        )
        form = TotemForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            return redirect('totems-list')

        totem.name = form.cleaned_data['name']
        totem.location = form.cleaned_data['location']
        totem.save()
        cache.clear()
        messages.success(request, 'Totem atualizado com sucesso.')
        if is_ajax_request(request):
            return render_totems_table(request)
        return redirect('totems-list')


class TotemDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, totem_id):
        totem = get_object_or_404(
            Totem.all_objects,
            pk=totem_id,
            company_id=request.current_company_id,
        )
        totem.is_active = not totem.is_active
        totem.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if totem.is_active:
            messages.success(request, 'Totem ativado com sucesso.')
        else:
            messages.success(request, 'Totem desativado com sucesso.')
        if is_ajax_request(request):
            return render_totems_table(request)
        return redirect('totems-list')


def render_mood_types_table(request, company_id):
    mood_types_qs = MoodType.all_objects.filter(company_id=company_id).order_by('label')
    page_obj = paginate_queryset(request, mood_types_qs)
    return render(
        request,
        'mood_types/_table_container.html',
        {
            'mood_types': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_complaint_types_table(request, company_id):
    complaint_types_qs = ComplaintType.all_objects.filter(company_id=company_id).order_by('label')
    page_obj = paginate_queryset(request, complaint_types_qs)
    return render(
        request,
        'complaint_types/_table_container.html',
        {
            'complaint_types': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_totems_table(request):
    totems_qs = Totem.all_objects.filter(company_id=request.current_company_id).order_by('name')
    page_obj = paginate_queryset(request, totems_qs)
    return render(
        request,
        'totems/_table_container.html',
        {
            'totems': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'totems',
            'can_manage_access': True,
        },
    )


def get_departments_filters(request):
    status = (request.GET.get('status') or '').strip().lower()
    if status not in {'active', 'inactive'}:
        status = ''
    search = (request.GET.get('name') or '').strip()
    return {
        'status': status,
        'name': search,
    }


def get_departments_queryset(company_id, filters):
    queryset = Department.all_objects.filter(company_id=company_id)
    if filters['status'] == 'active':
        queryset = queryset.filter(is_active=True)
    elif filters['status'] == 'inactive':
        queryset = queryset.filter(is_active=False)
    if filters['name']:
        queryset = queryset.filter(name__icontains=filters['name'])
    return queryset.order_by('name')


def get_job_functions_filters(request):
    status = (request.GET.get('status') or '').strip().lower()
    if status not in {'active', 'inactive'}:
        status = ''
    search = (request.GET.get('name') or '').strip()
    return {
        'status': status,
        'name': search,
    }


def get_job_functions_queryset(company_id, filters):
    queryset = JobFunction.all_objects.filter(company_id=company_id).prefetch_related('ghes', 'departments')
    if filters['status'] == 'active':
        queryset = queryset.filter(is_active=True)
    elif filters['status'] == 'inactive':
        queryset = queryset.filter(is_active=False)
    if filters['name']:
        queryset = queryset.filter(name__icontains=filters['name'])
    return queryset.order_by('name')


def get_complaint_filters(request):
    valid_statuses = {choice[0] for choice in Complaint.STATUS_CHOICES}
    status = (request.GET.get('status') or '').strip()
    if status not in valid_statuses:
        status = ''

    category = (request.GET.get('category') or '').strip().lower()
    department = (request.GET.get('department') or '').strip()

    raw_totem = (request.GET.get('totem') or '').strip()
    selected_totem = ''
    totem_id = None
    if raw_totem:
        try:
            totem_id = int(raw_totem)
            selected_totem = str(totem_id)
        except (TypeError, ValueError):
            totem_id = None

    return {
        'status': status,
        'category': category,
        'department': department,
        'totem': selected_totem,
        'totem_id': totem_id,
    }


def get_complaint_filter_options(company_id):
    complaint_types = list(
        ComplaintType.all_objects.filter(company_id=company_id).order_by('label')
    )
    complaint_type_filter_choices = [
        (normalize_complaint_type_key(item.label), item.label)
        for item in complaint_types
    ]
    department_choices = list(
        Department.all_objects.filter(company_id=company_id, is_active=True).order_by('name')
    )
    totems = Totem.all_objects.filter(company_id=company_id).order_by('name')
    return {
        'complaint_type_choices': complaint_type_filter_choices,
        'department_choices': department_choices,
        'totem_choices': totems,
    }


def get_help_request_filters(request):
    valid_statuses = {choice[0] for choice in HelpRequest.Status.choices}
    status = (request.GET.get('status') or '').strip()
    if status not in valid_statuses:
        status = ''

    department = (request.GET.get('department') or '').strip()

    raw_totem = (request.GET.get('totem') or '').strip()
    selected_totem = ''
    totem_id = None
    if raw_totem:
        try:
            totem_id = int(raw_totem)
            selected_totem = str(totem_id)
        except (TypeError, ValueError):
            totem_id = None

    return {
        'status': status,
        'department': department,
        'totem': selected_totem,
        'totem_id': totem_id,
    }


def get_help_requests_queryset(company_id, filters):
    queryset = HelpRequest.all_objects.select_related('totem').filter(company_id=company_id)

    if filters['status']:
        queryset = queryset.filter(status=filters['status'])
    if filters['department']:
        queryset = queryset.filter(department_name=filters['department'])
    if filters['totem_id'] is not None:
        queryset = queryset.filter(totem_id=filters['totem_id'])

    return queryset.order_by('-created_at')


def get_help_request_filter_options(company_id):
    department_choices = list(
        HelpRequest.all_objects.filter(company_id=company_id)
        .exclude(department_name='')
        .order_by('department_name')
        .values_list('department_name', flat=True)
        .distinct()
    )
    totem_choices = Totem.all_objects.filter(company_id=company_id).order_by('name')

    return {
        'department_choices': department_choices,
        'totem_choices': totem_choices,
    }


def render_help_requests_table(request, company_id):
    filters = get_help_request_filters(request)
    help_requests_qs = get_help_requests_queryset(company_id, filters)
    page_obj = paginate_queryset(request, help_requests_qs, per_page=15)
    return render(
        request,
        'help_requests/_table_container.html',
        {
            'help_requests': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def normalize_complaint_type_key(label):
    return (label or '')[:40].lower().replace(' ', '_')


def complaint_type_display_name(category_key):
    return (category_key or '').replace('_', ' ').strip().title()


def load_complaints_for_company(company_id, filters=None):
    complaint_type_map = {
        normalize_complaint_type_key(item.label): item.label
        for item in ComplaintType.all_objects.filter(company_id=company_id).only('label')
    }
    complaints_qs = (
        Complaint.all_objects.select_related('totem')
        .prefetch_related('action_histories__created_by')
        .filter(company_id=company_id)
    )
    if filters:
        if filters.get('status'):
            complaints_qs = complaints_qs.filter(complaint_status=filters['status'])
        if filters.get('category'):
            complaints_qs = complaints_qs.filter(category=filters['category'])
        if filters.get('department'):
            complaints_qs = complaints_qs.filter(details__icontains=f"Setor: {filters['department']}")
        if filters.get('totem_id') is not None:
            complaints_qs = complaints_qs.filter(totem_id=filters['totem_id'])
    complaints = list(complaints_qs.order_by('-record_date', '-created_at'))
    for complaint in complaints:
        complaint.complaint_type_label = complaint_type_map.get(
            complaint.category,
            complaint_type_display_name(complaint.category),
        )
        details_raw = (complaint.details or '').strip()
        complaint.department_label = '-'
        complaint.complaint_detail = details_raw or '-'
        if details_raw:
            parts = [part.strip() for part in details_raw.split('|') if part.strip()]
            relato = ''
            complemento = ''
            for part in parts:
                lower_part = part.lower()
                if lower_part.startswith('setor:'):
                    complaint.department_label = part.split(':', 1)[1].strip() or '-'
                elif lower_part.startswith('relato:'):
                    relato = part.split(':', 1)[1].strip()
                elif lower_part.startswith('complemento:'):
                    complemento = part.split(':', 1)[1].strip()
            if relato or complemento:
                complaint.complaint_detail = ' | '.join(
                    [value for value in [relato, complemento] if value]
                )
    return complaints


def render_complaints_table(request, company_id):
    filters = get_complaint_filters(request)
    complaints_all = load_complaints_for_company(company_id, filters=filters)
    page_obj = paginate_queryset(request, complaints_all)
    return render(
        request,
        'complaints/_table_container.html',
        {
            'complaints': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'status_choices': Complaint.STATUS_CHOICES,
        },
    )


def render_departments_table(request, company_id):
    filters = get_departments_filters(request)
    departments_qs = get_departments_queryset(company_id, filters)
    page_obj = paginate_queryset(request, departments_qs)
    return render(
        request,
        'departments/_table_container.html',
        {
            'departments': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_ghes_table(request, company_id):
    ghes_qs = GHE.all_objects.filter(company_id=company_id).order_by('name')
    page_obj = paginate_queryset(request, ghes_qs)
    return render(
        request,
        'ghes/_table_container.html',
        {
            'ghes': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_job_functions_table(request, company_id):
    filters = get_job_functions_filters(request)
    job_functions_qs = get_job_functions_queryset(company_id, filters)
    page_obj = paginate_queryset(request, job_functions_qs)
    return render(
        request,
        'job_functions/_table_container.html',
        {
            'job_functions': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_companies_table(request):
    companies_qs = Company.objects.order_by('name')
    search_name = (request.GET.get('name') or '').strip()
    selected_status = (request.GET.get('status') or '').strip().lower()
    if search_name:
        companies_qs = companies_qs.filter(name=search_name)
    if selected_status == 'active':
        companies_qs = companies_qs.filter(is_active=True)
    elif selected_status == 'inactive':
        companies_qs = companies_qs.filter(is_active=False)
    page_obj = paginate_queryset(request, companies_qs)
    return render(
        request,
        'companies/_table_container.html',
        {
            'companies': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_campaigns_table(request):
    filters = get_campaigns_filters(request)
    campaigns_qs = get_campaigns_queryset(filters)
    page_obj = paginate_queryset(request, campaigns_qs, per_page=15)
    return render(
        request,
        'campaigns/_table_container.html',
        {
            'campaigns': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_technical_responsibles_table(request):
    responsibles_qs = TechnicalResponsible.objects.filter(
        is_active=True
    ).order_by('sort_order', 'name')
    page_obj = paginate_queryset(request, responsibles_qs, per_page=15)
    return render(
        request,
        'master/_technical_table_container.html',
        {
            'technical_responsibles': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


def render_alert_settings_container(request, company_id):
    company = get_object_or_404(Company, pk=company_id, is_active=True)
    settings_obj = ensure_alert_settings(company)
    recipients_qs = AlertRecipient.all_objects.filter(company_id=company_id).order_by('email')
    page_obj = paginate_queryset(request, recipients_qs)
    return render(
        request,
        'settings/_alerts_container.html',
        {
            'settings_obj': settings_obj,
            'recipients': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
        },
    )


class MoodTypeListView(CompanyAdminRequiredMixin, View):
    template_name = 'mood_types/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        mood_types_qs = MoodType.all_objects.filter(
            company_id=request.current_company_id
        ).order_by('label')
        page_obj = paginate_queryset(request, mood_types_qs)
        context = {
            'mood_types': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'mood_types',
            'can_manage_access': True,
            'emoji_suggestions': MoodTypeForm.EMOJI_SUGGESTIONS,
            'sentiment_choices': MoodTypeForm.SENTIMENT_CHOICES,
        }
        sentiment_label_map = {key: label for key, label in MoodTypeForm.SENTIMENT_CHOICES}
        for mood_type in context['mood_types']:
            mood_type.sentiment_label = sentiment_label_map.get(mood_type.sentiment, mood_type.sentiment)
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'mood_types/_table_container.html', context)
        return render(request, self.template_name, context)


class MoodTypeCreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = MoodTypeForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_mood_types_table(request, request.current_company_id)
            return redirect('mood-types-list')

        label = (form.cleaned_data['label'] or '').strip()
        if MoodType.all_objects.filter(company_id=request.current_company_id, label__iexact=label).exists():
            messages.error(request, 'Ja existe tipo de humor com este nome.')
            if is_ajax_request(request):
                return render_mood_types_table(request, request.current_company_id)
            return redirect('mood-types-list')

        MoodType.all_objects.create(
            company_id=request.current_company_id,
            label=label,
            emoji=form.cleaned_data['emoji'],
            sentiment=form.cleaned_data['sentiment'],
            mood_score=form.cleaned_data['mood_score'],
            is_active=True,
        )
        cache.clear()
        messages.success(request, 'Tipo de humor criado com sucesso.')
        if is_ajax_request(request):
            return render_mood_types_table(request, request.current_company_id)
        return redirect('mood-types-list')


class MoodTypeUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, mood_type_id):
        mood_type = get_object_or_404(
            MoodType.all_objects,
            pk=mood_type_id,
            company_id=request.current_company_id,
        )
        form = MoodTypeForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_mood_types_table(request, request.current_company_id)
            return redirect('mood-types-list')

        label = (form.cleaned_data['label'] or '').strip()
        if MoodType.all_objects.filter(
            company_id=request.current_company_id,
            label__iexact=label,
        ).exclude(pk=mood_type.id).exists():
            messages.error(request, 'Ja existe tipo de humor com este nome.')
            if is_ajax_request(request):
                return render_mood_types_table(request, request.current_company_id)
            return redirect('mood-types-list')

        mood_type.label = label
        mood_type.emoji = form.cleaned_data['emoji']
        mood_type.sentiment = form.cleaned_data['sentiment']
        mood_type.mood_score = form.cleaned_data['mood_score']
        mood_type.save()
        cache.clear()
        messages.success(request, 'Tipo de humor atualizado com sucesso.')
        if is_ajax_request(request):
            return render_mood_types_table(request, request.current_company_id)
        return redirect('mood-types-list')


class MoodTypeDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, mood_type_id):
        mood_type = get_object_or_404(
            MoodType.all_objects,
            pk=mood_type_id,
            company_id=request.current_company_id,
        )
        mood_type.is_active = not mood_type.is_active
        mood_type.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if mood_type.is_active:
            messages.success(request, 'Tipo de humor ativado com sucesso.')
        else:
            messages.success(request, 'Tipo de humor desativado com sucesso.')
        if is_ajax_request(request):
            return render_mood_types_table(request, request.current_company_id)
        return redirect('mood-types-list')


class ComplaintTypeListView(CompanyAdminRequiredMixin, View):
    template_name = 'complaint_types/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        complaint_types_qs = ComplaintType.all_objects.filter(
            company_id=request.current_company_id
        ).order_by('label')
        page_obj = paginate_queryset(request, complaint_types_qs)
        context = {
            'complaint_types': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'complaint_types',
            'can_manage_access': True,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'complaint_types/_table_container.html', context)
        return render(request, self.template_name, context)


class ComplaintTypeCreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = ComplaintTypeForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_complaint_types_table(request, request.current_company_id)
            return redirect('complaint-types-list')

        label = (form.cleaned_data['label'] or '').strip()
        if ComplaintType.all_objects.filter(company_id=request.current_company_id, label__iexact=label).exists():
            messages.error(request, 'Já existe tipo de denúncia com este nome.')
            if is_ajax_request(request):
                return render_complaint_types_table(request, request.current_company_id)
            return redirect('complaint-types-list')

        ComplaintType.all_objects.create(
            company_id=request.current_company_id,
            label=label,
            is_active=True,
        )
        cache.clear()
        messages.success(request, 'Tipo de denúncia criado com sucesso.')
        if is_ajax_request(request):
            return render_complaint_types_table(request, request.current_company_id)
        return redirect('complaint-types-list')


class ComplaintTypeUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, complaint_type_id):
        complaint_type = get_object_or_404(
            ComplaintType.all_objects,
            pk=complaint_type_id,
            company_id=request.current_company_id,
        )
        form = ComplaintTypeForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_complaint_types_table(request, request.current_company_id)
            return redirect('complaint-types-list')

        label = (form.cleaned_data['label'] or '').strip()
        if ComplaintType.all_objects.filter(
            company_id=request.current_company_id,
            label__iexact=label,
        ).exclude(pk=complaint_type.id).exists():
            messages.error(request, 'Ja existe tipo de denúncia com este nome.')
            if is_ajax_request(request):
                return render_complaint_types_table(request, request.current_company_id)
            return redirect('complaint-types-list')

        complaint_type.label = label
        complaint_type.save()
        cache.clear()
        messages.success(request, 'Tipo de denúncia atualizado com sucesso.')
        if is_ajax_request(request):
            return render_complaint_types_table(request, request.current_company_id)
        return redirect('complaint-types-list')


class ComplaintTypeDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, complaint_type_id):
        complaint_type = get_object_or_404(
            ComplaintType.all_objects,
            pk=complaint_type_id,
            company_id=request.current_company_id,
        )
        complaint_type.is_active = not complaint_type.is_active
        complaint_type.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if complaint_type.is_active:
            messages.success(request, 'Tipo de denúncia ativado com sucesso.')
        else:
            messages.success(request, 'Tipo de denúncia desativado com sucesso.')
        if is_ajax_request(request):
            return render_complaint_types_table(request, request.current_company_id)
        return redirect('complaint-types-list')


class ComplaintListView(CompanyAdminRequiredMixin, View):
    template_name = 'complaints/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        filters = get_complaint_filters(request)
        complaints_all = load_complaints_for_company(request.current_company_id, filters=filters)
        page_obj = paginate_queryset(request, complaints_all)
        filter_options = get_complaint_filter_options(request.current_company_id)
        context = {
            'complaints': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'complaints',
            'can_manage_access': True,
            'status_choices': Complaint.STATUS_CHOICES,
            'complaint_type_choices': filter_options['complaint_type_choices'],
            'department_choices': filter_options['department_choices'],
            'totem_choices': filter_options['totem_choices'],
            'selected_status': filters['status'],
            'selected_category': filters['category'],
            'selected_department': filters['department'],
            'selected_totem': filters['totem'],
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'complaints/_table_container.html', context)
        return render(request, self.template_name, context)


class ReportListView(CompanyAdminRequiredMixin, View):
    template_name = 'reports/list.html'

    def get(self, request):
        reports_qs = Report.all_objects.filter(
            company_id=request.current_company_id
        ).order_by('-record_date', '-created_at')
        page_obj = paginate_queryset(request, reports_qs, per_page=15)
        context = {
            'reports': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'reports',
            'can_manage_access': True,
            'report_template_choices': Report.REPORT_TEMPLATE_CHOICES,
            'report_type_choices': Report.REPORT_TYPE_CHOICES,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'reports/_table_container.html', context)
        return render(request, self.template_name, context)

    def post(self, request):
        form = ReportGenerateForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            return redirect('reports-list')

        report_template = form.cleaned_data['report_template']
        report_type = form.cleaned_data['report_type']
        today = date.today()
        period_start, period_end = self._resolve_period(report_type, form.cleaned_data['period_start'], form.cleaned_data['period_end'], today)
        title = (form.cleaned_data.get('title') or '').strip()
        if not title:
            template_label = dict(Report.REPORT_TEMPLATE_CHOICES).get(report_template, report_template)
            period_label = dict(Report.REPORT_TYPE_CHOICES).get(report_type, report_type)
            title = f'{template_label} ({period_label}) - {period_start.strftime("%d/%m/%Y")} a {period_end.strftime("%d/%m/%Y")}'

        Report.all_objects.create(
            company_id=request.current_company_id,
            report_template=report_template,
            report_type=report_type,
            status='ready',
            title=title,
            generated_at=timezone.now(),
            storage_path='',
            record_date=today,
            period_start=period_start,
            period_end=period_end,
        )
        messages.success(request, 'Relatorio gerado com sucesso.')
        return redirect('reports-list')

    @staticmethod
    def _resolve_period(report_type, custom_start, custom_end, today):
        if custom_start and custom_end:
            return custom_start, custom_end
        if report_type == 'daily':
            return today, today
        if report_type == 'weekly':
            return today - timedelta(days=6), today
        if report_type == 'monthly':
            return today.replace(day=1), today
        return today - timedelta(days=29), today


class ReportDetailView(CompanyAdminRequiredMixin, View):
    template_name = 'reports/detail.html'
    other_template_name = 'reports/detail_other.html'
    SENTIMENT_LABELS = {
        'very_good': 'Muito bem',
        'good': 'Bem',
        'neutral': 'Regular',
        'bad': 'Triste',
        'very_bad': 'Irritado',
    }

    @staticmethod
    def _build_metrics(company_id, report):
        return build_report_metrics(company_id, report, ReportDetailView.SENTIMENT_LABELS)

    def get(self, request, report_id):
        report = get_object_or_404(
            Report.all_objects,
            pk=report_id,
            company_id=request.current_company_id,
        )
        metrics = self._build_metrics(request.current_company_id, report)
        recommendations = self._parse_recommendations(report.technical_recommendations)
        context = {
            'report': report,
            'metrics': metrics,
            'auto_print': request.GET.get('print') == '1',
            'recommendations': recommendations,
        }
        template_name = self.template_name
        if report.report_template == 'other':
            template_name = self.other_template_name
        return render(request, template_name, context)

    def post(self, request, report_id):
        report = get_object_or_404(
            Report.all_objects,
            pk=report_id,
            company_id=request.current_company_id,
        )
        is_ajax = is_ajax_request(request)
        if report.report_template != 'technical':
            if is_ajax:
                return JsonResponse(
                    {'ok': False, 'message': 'Edicao de analise IA disponivel apenas para o relatorio tecnico.'},
                    status=400,
                )
            messages.error(request, 'Edicao de analise IA disponivel apenas para o relatorio tecnico.')
            return redirect('reports-detail', report_id=report.id)

        action = (request.POST.get('action') or 'save').strip().lower()
        if action in {'generate_mood_analysis', 'generate_complaint_analysis', 'generate_recommendations'}:
            metrics = self._build_metrics(request.current_company_id, report)
            if action == 'generate_mood_analysis':
                generated_text = self._generate_single_with_gemini('mood', report, metrics)
                if not generated_text:
                    if is_ajax:
                        return JsonResponse(
                            {'ok': False, 'message': 'Nao foi possivel gerar a secao de humor com IA.'},
                            status=400,
                        )
                    messages.error(request, 'Nao foi possivel gerar a secao de humor com IA.')
                    return redirect('reports-detail', report_id=report.id)
                report.mood_analysis = generated_text
                report.save(update_fields=['mood_analysis', 'updated_at'])
                if is_ajax:
                    return JsonResponse(
                        {
                            'ok': True,
                            'field': 'mood_analysis',
                            'value': generated_text,
                            'message': 'Secao de humor gerada por IA.',
                        }
                    )
                messages.success(request, 'Secao de humor gerada por IA.')
                return redirect('reports-detail', report_id=report.id)

            if action == 'generate_complaint_analysis':
                generated_text = self._generate_single_with_gemini('complaint', report, metrics)
                if not generated_text:
                    if is_ajax:
                        return JsonResponse(
                            {'ok': False, 'message': 'Nao foi possivel gerar a secao de denuncias com IA.'},
                            status=400,
                        )
                    messages.error(request, 'Nao foi possivel gerar a secao de denuncias com IA.')
                    return redirect('reports-detail', report_id=report.id)
                report.complaint_analysis = generated_text
                report.save(update_fields=['complaint_analysis', 'updated_at'])
                if is_ajax:
                    return JsonResponse(
                        {
                            'ok': True,
                            'field': 'complaint_analysis',
                            'value': generated_text,
                            'message': 'Secao de denuncias gerada por IA.',
                        }
                    )
                messages.success(request, 'Secao de denuncias gerada por IA.')
                return redirect('reports-detail', report_id=report.id)

            generated_lines = self._generate_single_with_gemini('recommendations', report, metrics)
            if not generated_lines:
                if is_ajax:
                    return JsonResponse(
                        {'ok': False, 'message': 'Nao foi possivel gerar recomendacoes com IA.'},
                        status=400,
                    )
                messages.error(request, 'Nao foi possivel gerar recomendacoes com IA.')
                return redirect('reports-detail', report_id=report.id)
            generated_text = '\n'.join(generated_lines)
            report.technical_recommendations = generated_text
            report.save(update_fields=['technical_recommendations', 'updated_at'])
            if is_ajax:
                return JsonResponse(
                    {
                        'ok': True,
                        'field': 'technical_recommendations',
                        'value': generated_text,
                        'message': 'Recomendacoes geradas por IA.',
                    }
                )
            messages.success(request, 'Recomendacoes geradas por IA.')
            return redirect('reports-detail', report_id=report.id)

        report.mood_analysis = (request.POST.get('mood_analysis') or '').strip()
        report.complaint_analysis = (request.POST.get('complaint_analysis') or '').strip()
        report.technical_recommendations = (request.POST.get('technical_recommendations') or '').strip()
        report.save(
            update_fields=[
                'mood_analysis',
                'complaint_analysis',
                'technical_recommendations',
                'updated_at',
            ]
        )
        messages.success(request, 'Conteudo do relatorio atualizado com sucesso.')
        return redirect('reports-detail', report_id=report.id)

    def _build_metrics(self, company_id, report):
        return build_report_metrics(company_id, report, self.SENTIMENT_LABELS)


class ReportCompareView(CompanyAdminRequiredMixin, View):
    template_name = 'reports/compare.html'

    def get(self, request):
        is_master = request.user.is_superuser
        companies = []
        selected_company_id = request.current_company_id
        selected_company = None

        if is_master:
            companies = list(Company.objects.order_by('name').only('id', 'name'))
            raw_company_id = (request.GET.get('company_id') or '').strip()
            if raw_company_id.isdigit():
                candidate_id = int(raw_company_id)
                if user_has_company_access(request.user, candidate_id):
                    request.session['company_id'] = candidate_id
                    request.current_company_id = candidate_id
                    selected_company_id = candidate_id
        selected_company = Company.objects.filter(pk=selected_company_id).first()
        assessment_label = ''
        if selected_company:
            assessment_type = (selected_company.assessment_type or '').strip().lower()
            assessment_label = {
                'setor': 'Setor',
                'ghe': 'GHE',
            }.get(assessment_type, assessment_type.upper() if assessment_type else '')

        campaigns_qs = Campaign.all_objects.filter(
            company_id=selected_company_id,
            status=Campaign.Status.FINISHED,
        ).order_by('-end_date', '-created_at')
        campaigns = list(campaigns_qs)

        campaign_a_id = (request.GET.get('report_a') or '').strip()
        campaign_b_id = (request.GET.get('report_b') or '').strip()
        campaign_a = self._resolve_campaign(campaigns_qs, campaign_a_id)
        campaign_b = self._resolve_campaign(campaigns_qs, campaign_b_id)

        comparison = None
        campaign_a_comments = []
        campaign_b_comments = []
        if campaign_a and campaign_b and campaign_a.id != campaign_b.id:
            metrics_a = build_campaign_metrics(campaign_a)
            metrics_b = build_campaign_metrics(campaign_b)
            comparison = build_campaign_comparison(metrics_a, metrics_b)
        if campaign_a:
            comments = (
                CampaignResponse.all_objects.filter(campaign=campaign_a)
                .exclude(comments__isnull=True)
                .exclude(comments__exact='')
                .values_list('comments', flat=True)
            )
            campaign_a_comments = [str(item).strip() for item in comments if str(item).strip()]
        if campaign_b:
            comments = (
                CampaignResponse.all_objects.filter(campaign=campaign_b)
                .exclude(comments__isnull=True)
                .exclude(comments__exact='')
                .values_list('comments', flat=True)
            )
            campaign_b_comments = [str(item).strip() for item in comments if str(item).strip()]

        context = {
            'campaigns': campaigns,
            'campaign_a': campaign_a,
            'campaign_b': campaign_b,
            'comparison': comparison,
            'campaign_a_comments': campaign_a_comments,
            'campaign_b_comments': campaign_b_comments,
            'companies': companies,
            'selected_company_id': selected_company_id,
            'selected_company': selected_company,
            'assessment_label': assessment_label,
            'company_id': request.current_company_id,
            'active_menu': 'reports',
            'can_manage_access': True,
        }
        return render(request, self.template_name, context)

    @staticmethod
    def _resolve_campaign(campaigns_qs, campaign_id):
        if not campaign_id or not campaign_id.isdigit():
            return None
        return campaigns_qs.filter(pk=int(campaign_id)).first()

    def _generate_content_with_gemini(self, report, metrics):
        mood_distribution = metrics.get('mood_distribution') or []
        complaint_distribution = metrics.get('complaint_distribution') or []
        prompt = (
            'Voce e especialista em analise psicossocial ocupacional, com foco na NR-1, GRO e PGR. '
            'Seu objetivo neste relatorio e levantar riscos psicossociais com base nos indicadores apresentados. '
            'Analise SOMENTE os dados numericos enviados nas distribuicoes dos graficos. '
            'Nao invente contexto, nao cite causas sem evidencias e nao use informacoes externas. '
            'Se os dados forem insuficientes, diga isso de forma objetiva. '
            'Retorne APENAS JSON valido, sem markdown, com as chaves: '
            'mood_analysis (string), complaint_analysis (string), recommendations (array de 4 strings). '
            'mood_analysis: 2 a 3 frases curtas, analise sintetica, tecnica e enxuta, baseada apenas no grafico de humor. '
            'complaint_analysis: 2 a 3 frases curtas, analise sintetica, tecnica e enxuta, baseada apenas no grafico de denuncias. '
            'recommendations: 4 itens curtos (maximo 14 palavras por item), acionaveis e estritamente coerentes com os graficos. '
            f'Periodo: {report.period_start.strftime("%d/%m/%Y")} a {report.period_end.strftime("%d/%m/%Y")}. '
            f'Distribuicao de humor: {json.dumps(mood_distribution, ensure_ascii=False)}. '
            f'Distribuicao de denuncias: {json.dumps(complaint_distribution, ensure_ascii=False)}.'
        )

        api_key = os.getenv('GEMINI_API_KEY', '').strip()
        if not api_key or genai is None:
            return None

        model_name = os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview').strip() or 'gemini-3-flash-preview'
        try:
            client = genai.Client(api_key=api_key)
            config = None
            if genai_types is not None:
                config = genai_types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type='application/json',
                )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
        except Exception:
            return None

        text = str(getattr(response, 'text', '') or '').strip()
        if not text:
            text = self._extract_text_from_response(response)
        ai_json = self._safe_json_load(text)
        if not ai_json:
            return None

        mood_analysis = str(ai_json.get('mood_analysis') or '').strip()
        complaint_analysis = str(ai_json.get('complaint_analysis') or '').strip()
        raw_recommendations = (
            ai_json.get('recommendations')
            or ai_json.get('recomendacoes')
            or ai_json.get('technical_recommendations')
            or []
        )
        recommendations = self._normalize_recommendations(raw_recommendations)
        if not recommendations and mood_analysis and complaint_analysis:
            recommendations = self._build_min_recommendations(metrics)
        if not mood_analysis or not complaint_analysis or not recommendations:
            return None
        return {
            'mood_analysis': mood_analysis,
            'complaint_analysis': complaint_analysis,
            'recommendations': recommendations,
        }

    def _generate_single_with_gemini(self, section, report, metrics):
        mood_distribution = metrics.get('mood_distribution') or []
        complaint_distribution = metrics.get('complaint_distribution') or []
        api_key = os.getenv('GEMINI_API_KEY', '').strip()
        if not api_key or genai is None:
            return None

        section_instructions = {
            'mood': (
                'Retorne APENAS JSON com a chave mood_analysis (string). '
                'Analise somente o grafico de humor em 2 ou 3 frases curtas, tecnicas e objetivas.'
            ),
            'complaint': (
                'Retorne APENAS JSON com a chave complaint_analysis (string). '
                'Analise somente o grafico de denuncias em 2 ou 3 frases curtas, tecnicas e objetivas.'
            ),
            'recommendations': (
                'Retorne APENAS JSON com a chave recommendations (array de 4 strings). '
                'Crie 4 recomendacoes curtas e acionaveis baseadas estritamente nos graficos.'
            ),
        }
        prompt = (
            'Voce e especialista em analise psicossocial ocupacional, com foco na NR-1, GRO e PGR. '
            'Seu objetivo e levantar riscos psicossociais de forma tecnica, sintetica e acionavel. '
            'Analise SOMENTE os dados numericos enviados, sem inferencias externas. '
            f'{section_instructions.get(section, "")} '
            f'Periodo: {report.period_start.strftime("%d/%m/%Y")} a {report.period_end.strftime("%d/%m/%Y")}. '
            f'Distribuicao de humor: {json.dumps(mood_distribution, ensure_ascii=False)}. '
            f'Distribuicao de denuncias: {json.dumps(complaint_distribution, ensure_ascii=False)}.'
        )

        model_name = os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview').strip() or 'gemini-3-flash-preview'
        try:
            client = genai.Client(api_key=api_key)
            config = None
            if genai_types is not None:
                config = genai_types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type='application/json',
                )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
        except Exception:
            return None

        text = str(getattr(response, 'text', '') or '').strip()
        if not text:
            text = self._extract_text_from_response(response)
        ai_json = self._safe_json_load(text)
        if not ai_json:
            return None

        if section == 'mood':
            value = str(ai_json.get('mood_analysis') or '').strip()
            return value or None
        if section == 'complaint':
            value = str(ai_json.get('complaint_analysis') or '').strip()
            return value or None
        raw_recommendations = (
            ai_json.get('recommendations')
            or ai_json.get('recomendacoes')
            or ai_json.get('technical_recommendations')
            or []
        )
        normalized = self._normalize_recommendations(raw_recommendations)
        return normalized or None

    def _extract_text_from_response(self, response):
        try:
            candidates = getattr(response, 'candidates', None) or []
            fragments = []
            for candidate in candidates:
                content = getattr(candidate, 'content', None)
                if content is None and isinstance(candidate, dict):
                    content = candidate.get('content')
                if content is None:
                    continue
                parts = getattr(content, 'parts', None)
                if parts is None and isinstance(content, dict):
                    parts = content.get('parts')
                for part in parts or []:
                    text = getattr(part, 'text', None)
                    if text is None and isinstance(part, dict):
                        text = part.get('text')
                    if text:
                        fragments.append(str(text).strip())
            return '\n'.join([item for item in fragments if item])
        except Exception:
            return ''

    def _safe_json_load(self, text):
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Fallback when model prepends/appends text around a JSON object.
        match = re.search(r'\{.*\}', cleaned, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _normalize_recommendations(self, raw_recommendations):
        items = []
        if isinstance(raw_recommendations, str):
            chunks = re.split(r'[\n;]+', raw_recommendations)
            for chunk in chunks:
                cleaned = re.sub(r'^\s*[\-\*\d\.\)]\s*', '', chunk.strip())
                if cleaned:
                    items.append(cleaned)
        else:
            for item in raw_recommendations:
                cleaned = re.sub(r'^\s*[\-\*\d\.\)]\s*', '', str(item).strip())
                if cleaned:
                    items.append(cleaned)
        return items[:6]

    def _build_min_recommendations(self, metrics):
        mood_top = (metrics.get('mood_distribution') or [])
        complaint_top = (metrics.get('complaint_distribution') or [])
        top_mood_label = mood_top[0]['label'] if mood_top else 'humor'
        top_complaint_label = complaint_top[0]['label'] if complaint_top else 'denuncias'
        return [
            f'Monitorar variacao semanal do indicador predominante de {top_mood_label.lower()}.',
            f'Priorizar plano preventivo para ocorrencias de {top_complaint_label.lower()}.',
            'Definir meta mensal de reducao para os maiores percentuais observados.',
            'Reavaliar indicadores em 30 dias para validar tendencia dos graficos.',
        ]

    def _parse_recommendations(self, recommendations_text):
        lines = []
        for raw_line in (recommendations_text or '').splitlines():
            cleaned = raw_line.strip().lstrip('-').strip()
            if cleaned:
                lines.append(cleaned)
        return lines


class ComplaintUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, complaint_id):
        complaint = get_object_or_404(
            Complaint.all_objects,
            pk=complaint_id,
            company_id=request.current_company_id,
        )
        form = ComplaintUpdateForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_complaints_table(request, request.current_company_id)
            return redirect('complaints-list')

        action_note = (form.cleaned_data['action_note'] or '').strip()
        if not action_note:
            messages.error(request, 'Informe a ação tomada para registrar o histórico.')
            if is_ajax_request(request):
                return render_complaints_table(request, request.current_company_id)
            return redirect('complaints-list')

        complaint.complaint_status = form.cleaned_data['complaint_status']
        complaint.save(update_fields=['complaint_status', 'updated_at'])
        ComplaintActionHistory.all_objects.create(
            company_id=request.current_company_id,
            complaint=complaint,
            complaint_status=form.cleaned_data['complaint_status'],
            action_note=action_note,
            created_by=request.user,
        )
        cache.clear()
        messages.success(request, 'Denuncia atualizada com sucesso.')
        if is_ajax_request(request):
            return render_complaints_table(request, request.current_company_id)
        return redirect('complaints-list')


class ComplaintHistoryView(CompanyAdminRequiredMixin, View):
    def get(self, request, complaint_id):
        complaint = get_object_or_404(
            Complaint.all_objects.select_related('totem'),
            pk=complaint_id,
            company_id=request.current_company_id,
        )
        histories = ComplaintActionHistory.all_objects.select_related('created_by').filter(
            company_id=request.current_company_id,
            complaint=complaint,
        ).order_by('-created_at')
        complaint_type_label = getattr(complaint, 'complaint_type_label', None)
        if not complaint_type_label:
            complaint_type_map = {
                normalize_complaint_type_key(item.label): item.label
                for item in ComplaintType.all_objects.filter(company_id=request.current_company_id).only('label')
            }
            complaint_type_label = complaint_type_map.get(
                complaint.category,
                complaint_type_display_name(complaint.category),
            )

        return render(
            request,
            'complaints/_history_content.html',
            {
                'complaint': complaint,
                'complaint_type_label': complaint_type_label,
                'histories': histories,
            },
        )


class DepartmentListView(CompanyAdminRequiredMixin, View):
    template_name = 'departments/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        filters = get_departments_filters(request)
        departments_qs = get_departments_queryset(request.current_company_id, filters)
        page_obj = paginate_queryset(request, departments_qs)
        ghes = list(
            GHE.all_objects.filter(company_id=request.current_company_id, is_active=True)
            .order_by('name')
            .only('id', 'name')
        )
        context = {
            'departments': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'departments',
            'can_manage_access': True,
            'selected_status': filters['status'],
            'search_name': filters['name'],
            'ghes': ghes,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'departments/_table_container.html', context)
        return render(request, self.template_name, context)


class DepartmentCreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = DepartmentForm(request.POST)
        form.fields['ghe_id'].choices = [
            (ghe.id, ghe.name)
            for ghe in GHE.all_objects.filter(company_id=request.current_company_id).order_by('name')
        ]
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_departments_table(request, request.current_company_id)
            return redirect('departments-list')

        department_name = (form.cleaned_data['name'] or '').strip()
        if not department_name:
            messages.error(request, 'Nome do setor e obrigatorio.')
            if is_ajax_request(request):
                return render_departments_table(request, request.current_company_id)
            return redirect('departments-list')

        if Department.all_objects.filter(
            company_id=request.current_company_id,
            name__iexact=department_name,
        ).exists():
            messages.error(request, 'Ja existe setor com este nome na empresa.')
            if is_ajax_request(request):
                return render_departments_table(request, request.current_company_id)
            return redirect('departments-list')

        Department.all_objects.create(
            company_id=request.current_company_id,
            name=department_name,
            ghe_id=form.cleaned_data['ghe_id'],
            is_active=True,
        )
        cache.clear()
        messages.success(request, 'Setor criado com sucesso.')
        if is_ajax_request(request):
            return render_departments_table(request, request.current_company_id)
        return redirect('departments-list')


class DepartmentUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, department_id):
        department = get_object_or_404(
            Department.all_objects,
            pk=department_id,
            company_id=request.current_company_id,
        )
        form = DepartmentForm(request.POST)
        form.fields['ghe_id'].choices = [
            (ghe.id, ghe.name)
            for ghe in GHE.all_objects.filter(company_id=request.current_company_id).order_by('name')
        ]
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_departments_table(request, request.current_company_id)
            return redirect('departments-list')

        department_name = (form.cleaned_data['name'] or '').strip()
        if not department_name:
            messages.error(request, 'Nome do setor e obrigatorio.')
            if is_ajax_request(request):
                return render_departments_table(request, request.current_company_id)
            return redirect('departments-list')

        if Department.all_objects.filter(
            company_id=request.current_company_id,
            name__iexact=department_name,
        ).exclude(pk=department.id).exists():
            messages.error(request, 'Ja existe setor com este nome na empresa.')
            if is_ajax_request(request):
                return render_departments_table(request, request.current_company_id)
            return redirect('departments-list')

        department.name = department_name
        department.ghe_id = form.cleaned_data['ghe_id']
        department.is_active = form.cleaned_data['is_active']
        department.save()
        cache.clear()
        messages.success(request, 'Setor atualizado com sucesso.')
        if is_ajax_request(request):
            return render_departments_table(request, request.current_company_id)
        return redirect('departments-list')


class DepartmentDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, department_id):
        department = get_object_or_404(
            Department.all_objects,
            pk=department_id,
            company_id=request.current_company_id,
        )
        department.is_active = not department.is_active
        department.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if department.is_active:
            messages.success(request, 'Setor ativado com sucesso.')
        else:
            messages.success(request, 'Setor desativado com sucesso.')
        if is_ajax_request(request):
            return render_departments_table(request, request.current_company_id)
        return redirect('departments-list')


class GHEListView(CompanyAdminRequiredMixin, View):
    template_name = 'ghes/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        ghes_qs = GHE.all_objects.filter(company_id=request.current_company_id).order_by('name')
        page_obj = paginate_queryset(request, ghes_qs)
        context = {
            'ghes': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'ghes',
            'can_manage_access': True,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'ghes/_table_container.html', context)
        return render(request, self.template_name, context)


class GHEOptionsView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        ghes = list(
            GHE.all_objects.filter(company_id=request.current_company_id, is_active=True)
            .order_by('name')
            .only('id', 'name')
        )
        return JsonResponse(
            {
                'ghes': [{'id': ghe.id, 'name': ghe.name} for ghe in ghes],
            }
        )


class GHECreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = GHEForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_ghes_table(request, request.current_company_id)
            return redirect('ghes-list')

        name = (form.cleaned_data['name'] or '').strip()
        if not name:
            messages.error(request, 'Nome do GHE e obrigatorio.')
            if is_ajax_request(request):
                return render_ghes_table(request, request.current_company_id)
            return redirect('ghes-list')

        if GHE.all_objects.filter(
            company_id=request.current_company_id,
            name__iexact=name,
        ).exists():
            messages.error(request, 'Ja existe GHE com este nome na empresa.')
            if is_ajax_request(request):
                return render_ghes_table(request, request.current_company_id)
            return redirect('ghes-list')

        GHE.all_objects.create(
            company_id=request.current_company_id,
            name=name,
            is_active=True,
        )
        cache.clear()
        messages.success(request, 'GHE criado com sucesso.')
        if is_ajax_request(request):
            return render_ghes_table(request, request.current_company_id)
        return redirect('ghes-list')


class GHEUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, ghe_id):
        ghe = get_object_or_404(
            GHE.all_objects,
            pk=ghe_id,
            company_id=request.current_company_id,
        )
        form = GHEForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_ghes_table(request, request.current_company_id)
            return redirect('ghes-list')

        name = (form.cleaned_data['name'] or '').strip()
        if not name:
            messages.error(request, 'Nome do GHE e obrigatorio.')
            if is_ajax_request(request):
                return render_ghes_table(request, request.current_company_id)
            return redirect('ghes-list')

        if GHE.all_objects.filter(
            company_id=request.current_company_id,
            name__iexact=name,
        ).exclude(pk=ghe.id).exists():
            messages.error(request, 'Ja existe GHE com este nome na empresa.')
            if is_ajax_request(request):
                return render_ghes_table(request, request.current_company_id)
            return redirect('ghes-list')

        ghe.name = name
        ghe.save()
        cache.clear()
        messages.success(request, 'GHE atualizado com sucesso.')
        if is_ajax_request(request):
            return render_ghes_table(request, request.current_company_id)
        return redirect('ghes-list')


class GHEDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, ghe_id):
        ghe = get_object_or_404(
            GHE.all_objects,
            pk=ghe_id,
            company_id=request.current_company_id,
        )
        ghe.is_active = not ghe.is_active
        ghe.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if ghe.is_active:
            messages.success(request, 'GHE ativado com sucesso.')
        else:
            messages.success(request, 'GHE desativado com sucesso.')
        if is_ajax_request(request):
            return render_ghes_table(request, request.current_company_id)
        return redirect('ghes-list')


class JobFunctionListView(CompanyAdminRequiredMixin, View):
    template_name = 'job_functions/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        filters = get_job_functions_filters(request)
        job_functions_qs = get_job_functions_queryset(request.current_company_id, filters)
        page_obj = paginate_queryset(request, job_functions_qs)
        ghes = list(
            GHE.all_objects.filter(company_id=request.current_company_id, is_active=True)
            .order_by('name')
            .only('id', 'name')
        )
        departments = list(
            Department.all_objects.filter(company_id=request.current_company_id, is_active=True)
            .order_by('name')
            .only('id', 'name')
        )
        context = {
            'job_functions': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'job_functions',
            'can_manage_access': True,
            'selected_status': filters['status'],
            'search_name': filters['name'],
            'ghes': ghes,
            'departments': departments,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'job_functions/_table_container.html', context)
        return render(request, self.template_name, context)


class JobFunctionCreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = JobFunctionForm(request.POST)
        form.fields['ghes'].choices = [
            (ghe.id, ghe.name)
            for ghe in GHE.all_objects.filter(company_id=request.current_company_id).order_by('name')
        ]
        form.fields['departments'].choices = [
            (department.id, department.name)
            for department in Department.all_objects.filter(company_id=request.current_company_id).order_by('name')
        ]
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        name = (form.cleaned_data['name'] or '').strip()
        if not name:
            messages.error(request, 'Nome da funcao e obrigatorio.')
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        ghes_ids = [int(value) for value in form.cleaned_data.get('ghes') or []]
        departments_ids = [int(value) for value in form.cleaned_data.get('departments') or []]
        if not ghes_ids and not departments_ids:
            messages.error(request, 'Selecione ao menos um GHE ou um setor.')
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        if JobFunction.all_objects.filter(
            company_id=request.current_company_id,
            name__iexact=name,
        ).exists():
            messages.error(request, 'Ja existe funcao com este nome na empresa.')
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        job_function = JobFunction.all_objects.create(
            company_id=request.current_company_id,
            name=name,
            is_active=True,
        )
        if ghes_ids:
            job_function.ghes.set(ghes_ids)
        if departments_ids:
            job_function.departments.set(departments_ids)
        cache.clear()
        messages.success(request, 'Funcao criada com sucesso.')
        if is_ajax_request(request):
            return render_job_functions_table(request, request.current_company_id)
        return redirect('job-functions-list')


class JobFunctionUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, job_function_id):
        job_function = get_object_or_404(
            JobFunction.all_objects,
            pk=job_function_id,
            company_id=request.current_company_id,
        )
        form = JobFunctionForm(request.POST)
        form.fields['ghes'].choices = [
            (ghe.id, ghe.name)
            for ghe in GHE.all_objects.filter(company_id=request.current_company_id).order_by('name')
        ]
        form.fields['departments'].choices = [
            (department.id, department.name)
            for department in Department.all_objects.filter(company_id=request.current_company_id).order_by('name')
        ]
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        name = (form.cleaned_data['name'] or '').strip()
        if not name:
            messages.error(request, 'Nome da funcao e obrigatorio.')
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        ghes_ids = [int(value) for value in form.cleaned_data.get('ghes') or []]
        departments_ids = [int(value) for value in form.cleaned_data.get('departments') or []]
        if not ghes_ids and not departments_ids:
            messages.error(request, 'Selecione ao menos um GHE ou um setor.')
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        if JobFunction.all_objects.filter(
            company_id=request.current_company_id,
            name__iexact=name,
        ).exclude(pk=job_function.id).exists():
            messages.error(request, 'Ja existe funcao com este nome na empresa.')
            if is_ajax_request(request):
                return render_job_functions_table(request, request.current_company_id)
            return redirect('job-functions-list')

        job_function.name = name
        job_function.is_active = form.cleaned_data['is_active']
        job_function.save()
        job_function.ghes.set(ghes_ids)
        job_function.departments.set(departments_ids)
        cache.clear()
        messages.success(request, 'Funcao atualizada com sucesso.')
        if is_ajax_request(request):
            return render_job_functions_table(request, request.current_company_id)
        return redirect('job-functions-list')


class JobFunctionDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, job_function_id):
        job_function = get_object_or_404(
            JobFunction.all_objects,
            pk=job_function_id,
            company_id=request.current_company_id,
        )
        job_function.is_active = not job_function.is_active
        job_function.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if job_function.is_active:
            messages.success(request, 'Funcao ativada com sucesso.')
        else:
            messages.success(request, 'Funcao desativada com sucesso.')
        if is_ajax_request(request):
            return render_job_functions_table(request, request.current_company_id)
        return redirect('job-functions-list')


class AlertSettingsView(CompanyAdminRequiredMixin, View):
    template_name = 'settings/alerts.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        company = get_object_or_404(Company, pk=request.current_company_id, is_active=True)
        settings_obj = ensure_alert_settings(company)
        recipients_qs = AlertRecipient.all_objects.filter(
            company_id=request.current_company_id
        ).order_by('email')
        page_obj = paginate_queryset(request, recipients_qs)
        context = {
            'settings_obj': settings_obj,
            'recipients': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'settings',
            'can_manage_access': True,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'settings/_alerts_container.html', context)
        return render(request, self.template_name, context)


class AlertSettingsUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        company = get_object_or_404(Company, pk=request.current_company_id, is_active=True)
        settings_obj = ensure_alert_settings(company)
        post_data = request.POST.copy()
        raw_negative_percent = (post_data.get('max_negative_mood_percent') or '').strip()
        if raw_negative_percent:
            post_data['max_negative_mood_percent'] = raw_negative_percent.replace(',', '.')
        form = AlertSettingForm(post_data)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_alert_settings_container(request, request.current_company_id)
            return redirect('settings-alerts')

        settings_obj.auto_alerts_enabled = form.cleaned_data['auto_alerts_enabled']
        settings_obj.is_active = form.cleaned_data['is_active']
        settings_obj.analysis_window_days = form.cleaned_data['analysis_window_days']
        settings_obj.max_critical_complaints = form.cleaned_data['max_critical_complaints']
        settings_obj.max_negative_mood_percent = form.cleaned_data['max_negative_mood_percent']
        settings_obj.max_open_help_requests = form.cleaned_data['max_open_help_requests']
        settings_obj.save()

        if settings_obj.is_active and settings_obj.auto_alerts_enabled:
            evaluate_automatic_alerts(company)
        cache.clear()
        messages.success(request, 'Configurações de alerta atualizadas com sucesso.')
        if is_ajax_request(request):
            return render_alert_settings_container(request, request.current_company_id)
        return redirect('settings-alerts')


class AlertRecipientCreateView(CompanyAdminRequiredMixin, View):
    def post(self, request):
        form = AlertRecipientForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_alert_settings_container(request, request.current_company_id)
            return redirect('settings-alerts')

        email = (form.cleaned_data['email'] or '').strip().lower()
        if AlertRecipient.all_objects.filter(
            company_id=request.current_company_id,
            email__iexact=email,
        ).exists():
            messages.error(request, 'Ja existe destinatario com este e-mail.')
            if is_ajax_request(request):
                return render_alert_settings_container(request, request.current_company_id)
            return redirect('settings-alerts')

        AlertRecipient.all_objects.create(
            company_id=request.current_company_id,
            name=(form.cleaned_data['name'] or '').strip(),
            email=email,
            is_active=form.cleaned_data['is_active'],
        )
        cache.clear()
        messages.success(request, 'Destinatario de alerta criado com sucesso.')
        if is_ajax_request(request):
            return render_alert_settings_container(request, request.current_company_id)
        return redirect('settings-alerts')


class AlertRecipientUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, recipient_id):
        recipient = get_object_or_404(
            AlertRecipient.all_objects,
            pk=recipient_id,
            company_id=request.current_company_id,
        )
        form = AlertRecipientForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_alert_settings_container(request, request.current_company_id)
            return redirect('settings-alerts')

        email = (form.cleaned_data['email'] or '').strip().lower()
        if AlertRecipient.all_objects.filter(
            company_id=request.current_company_id,
            email__iexact=email,
        ).exclude(pk=recipient.id).exists():
            messages.error(request, 'Ja existe destinatario com este e-mail.')
            if is_ajax_request(request):
                return render_alert_settings_container(request, request.current_company_id)
            return redirect('settings-alerts')

        recipient.name = (form.cleaned_data['name'] or '').strip()
        recipient.email = email
        recipient.is_active = form.cleaned_data['is_active']
        recipient.save()
        cache.clear()
        messages.success(request, 'Destinatario atualizado com sucesso.')
        if is_ajax_request(request):
            return render_alert_settings_container(request, request.current_company_id)
        return redirect('settings-alerts')


class AlertRecipientDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, recipient_id):
        recipient = get_object_or_404(
            AlertRecipient.all_objects,
            pk=recipient_id,
            company_id=request.current_company_id,
        )
        recipient.is_active = not recipient.is_active
        recipient.save(update_fields=['is_active', 'updated_at'])
        cache.clear()
        if recipient.is_active:
            messages.success(request, 'Destinatario ativado com sucesso.')
        else:
            messages.success(request, 'Destinatario desativado com sucesso.')
        if is_ajax_request(request):
            return render_alert_settings_container(request, request.current_company_id)
        return redirect('settings-alerts')


class HelpRequestListView(CompanyAdminRequiredMixin, View):
    template_name = 'help_requests/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        filters = get_help_request_filters(request)
        help_requests_qs = get_help_requests_queryset(request.current_company_id, filters)
        page_obj = paginate_queryset(request, help_requests_qs, per_page=15)
        filter_options = get_help_request_filter_options(request.current_company_id)
        context = {
            'help_requests': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'help_requests',
            'can_manage_access': True,
            'status_choices': HelpRequest.Status.choices,
            'department_choices': filter_options['department_choices'],
            'totem_choices': filter_options['totem_choices'],
            'selected_status': filters['status'],
            'selected_department': filters['department'],
            'selected_totem': filters['totem'],
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'help_requests/_table_container.html', context)
        return render(request, self.template_name, context)


class HelpRequestUpdateView(CompanyAdminRequiredMixin, View):
    def post(self, request, help_request_id):
        help_request = get_object_or_404(
            HelpRequest.all_objects,
            pk=help_request_id,
            company_id=request.current_company_id,
        )
        form = HelpRequestUpdateForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            if is_ajax_request(request):
                return render_help_requests_table(request, request.current_company_id)
            return redirect('help-requests-list')

        help_request.status = form.cleaned_data['status']
        help_request.admin_notes = form.cleaned_data['admin_notes']
        help_request.save(update_fields=['status', 'admin_notes', 'updated_at'])
        HelpRequestActionHistory.all_objects.create(
            company_id=request.current_company_id,
            help_request=help_request,
            status=form.cleaned_data['status'],
            admin_notes=form.cleaned_data['admin_notes'],
            created_by=request.user,
        )
        evaluate_automatic_alerts(help_request.company)
        cache.clear()
        messages.success(request, 'Pedido de ajuda atualizado com sucesso.')
        if is_ajax_request(request):
            return render_help_requests_table(request, request.current_company_id)
        return redirect('help-requests-list')


class HelpRequestHistoryView(CompanyAdminRequiredMixin, View):
    def get(self, request, help_request_id):
        help_request = get_object_or_404(
            HelpRequest.all_objects.select_related('totem'),
            pk=help_request_id,
            company_id=request.current_company_id,
        )
        histories = HelpRequestActionHistory.all_objects.select_related('created_by').filter(
            company_id=request.current_company_id,
            help_request=help_request,
        ).order_by('-created_at')
        return render(
            request,
            'help_requests/_history_content.html',
            {
                'help_request': help_request,
                'histories': histories,
            },
        )


class HelpRequestDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, help_request_id):
        help_request = get_object_or_404(
            HelpRequest.all_objects,
            pk=help_request_id,
            company_id=request.current_company_id,
        )
        help_request.delete()
        cache.clear()
        messages.success(request, 'Pedido de ajuda removido com sucesso.')
        return redirect('help-requests-list')


class InternalUserListView(CompanyAdminRequiredMixin, View):
    template_name = 'users/list.html'

    @method_decorator(vary_on_headers('Cookie'))
    @method_decorator(cache_page(30))
    def get(self, request):
        memberships_qs = (
            CompanyMembership.objects.select_related('user', 'company')
            .filter(company_id=request.current_company_id)
            .order_by('user__username')
        )
        page_obj = paginate_queryset(request, memberships_qs)
        context = {
            'memberships': page_obj.object_list,
            'page_obj': page_obj,
            'pagination_query': build_pagination_query(request),
            'company_id': request.current_company_id,
            'active_menu': 'users',
            'role_choices': InternalUserBaseForm.ROLE_CHOICES,
        }
        if is_ajax_request(request) or request.GET.get('partial') == '1':
            return render(request, 'users/_table_container.html', context)
        return render(request, self.template_name, context)


class InternalUserCreateView(CompanyAdminRequiredMixin, View):
    def get(self, request):
        return redirect('users-list')

    def post(self, request):
        form = InternalUserCreateForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            return redirect('users-list')

        company = get_object_or_404(Company, pk=request.current_company_id)
        if company.max_users:
            active_users = (
                CompanyMembership.objects.select_related('user')
                .filter(company_id=request.current_company_id, is_active=True, user__is_active=True)
                .count()
            )
            if active_users >= company.max_users:
                messages.error(request, 'Limite de usuarios atingido para esta empresa.')
                return redirect('users-list')

        user_model = get_user_model()
        username = form.cleaned_data['username']
        if user_model.objects.filter(username=username).exists():
            messages.error(request, 'Ja existe usuario com este username.')
            return redirect('users-list')

        with transaction.atomic():
            user = user_model.objects.create_user(
                username=username,
                password=form.cleaned_data['password'],
                email=form.cleaned_data['email'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_active=form.cleaned_data['is_active'],
            )
            CompanyMembership.objects.create(
                user=user,
                company_id=request.current_company_id,
                role=form.cleaned_data['role'],
                is_active=form.cleaned_data['is_active'],
            )

        cache.clear()
        messages.success(request, 'Usuario criado com sucesso.')
        return redirect('users-list')


class InternalUserUpdateView(CompanyAdminRequiredMixin, View):
    def get(self, request, membership_id):
        return redirect('users-list')

    def post(self, request, membership_id):
        membership = self._get_membership(request, membership_id)
        form = InternalUserUpdateForm(request.POST)
        if not form.is_valid():
            messages.error(request, collect_form_errors(form))
            return redirect('users-list')

        user_model = get_user_model()
        username = form.cleaned_data['username']
        if (
            username != membership.user.username
            and user_model.objects.filter(username=username).exists()
        ):
            messages.error(request, 'Ja existe usuario com este username.')
            return redirect('users-list')

        if membership.user_id == request.user.id and not form.cleaned_data['is_active']:
            messages.error(request, 'Voce nao pode desativar seu proprio acesso.')
            return redirect('users-list')

        with transaction.atomic():
            user = membership.user
            user.username = username
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            user.is_active = form.cleaned_data['is_active']
            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
            user.save()

            membership.role = form.cleaned_data['role']
            membership.is_active = form.cleaned_data['is_active']
            membership.save()

        cache.clear()
        messages.success(request, 'Usuario atualizado com sucesso.')
        return redirect('users-list')

    def _get_membership(self, request, membership_id):
        return get_object_or_404(
            CompanyMembership.objects.select_related('user'),
            pk=membership_id,
            company_id=request.current_company_id,
        )


class InternalUserDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, membership_id):
        membership = get_object_or_404(
            CompanyMembership,
            pk=membership_id,
            company_id=request.current_company_id,
        )
        if membership.user_id == request.user.id:
            messages.error(request, 'Voce nao pode remover seu proprio acesso.')
            return redirect('users-list')

        membership.delete()
        cache.clear()
        messages.success(request, 'Acesso removido com sucesso.')
        return redirect('users-list')
