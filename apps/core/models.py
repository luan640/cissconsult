from django.conf import settings
from django.db import models
from decimal import Decimal
from django.db.models import F, Q
from uuid import uuid4

from apps.tenancy.models import TenantModel


class StandardPeriodModel(TenantModel):
    record_date = models.DateField(db_index=True)
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=Q(period_start__lte=F('period_end')),
                name='%(app_label)s_%(class)s_period_valid',
            )
        ]


class Department(TenantModel):
    name = models.CharField(max_length=150)
    ghe = models.ForeignKey(
        'GHE',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class GHE(TenantModel):
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'ghes'
        ordering = ['name']
        unique_together = ('company', 'name')

    def __str__(self) -> str:
        return self.name


class JobFunction(TenantModel):
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    ghes = models.ManyToManyField('GHE', blank=True, related_name='job_functions')
    departments = models.ManyToManyField('Department', blank=True, related_name='job_functions')

    class Meta:
        db_table = 'job_functions'
        ordering = ['name']
        unique_together = (('company', 'name'),)

    def __str__(self) -> str:
        return self.name


class Campaign(TenantModel):
    class Status(models.TextChoices):
        PLANNED = 'PLANNED', 'Planejada'
        ACTIVE = 'ACTIVE', 'Ativa'
        PAUSED = 'PAUSED', 'Pausada'
        FINISHED = 'FINISHED', 'Encerrada'

    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_campaigns',
    )

    class Meta:
        db_table = 'campaigns'
        ordering = ['-start_date']
        constraints = [
            models.CheckConstraint(
                condition=Q(start_date__lte=F('end_date')),
                name='core_campaigns_period_valid',
            ),
        ]

    def __str__(self) -> str:
        return self.title


class CampaignResponse(TenantModel):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    cpf_hash = models.CharField(max_length=64)
    first_name = models.CharField(max_length=120, blank=True)
    age = models.PositiveSmallIntegerField()
    sex = models.CharField(max_length=20, blank=True)
    ghe = models.ForeignKey(
        'GHE',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_responses',
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_responses',
    )
    job_function = models.ForeignKey(
        'JobFunction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_responses',
    )
    responses = models.JSONField(default=dict, blank=True)
    comments = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'campaign_responses'
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'cpf_hash'],
                name='core_campaign_response_unique_cpf_per_campaign',
            ),
        ]


class CampaignReportAction(TenantModel):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='report_actions',
    )
    question_text = models.TextField()
    measures = models.JSONField(default=list, blank=True)
    implantation_months = models.JSONField(default=list, blank=True)
    status = models.JSONField(default=dict, blank=True)
    concluded_on = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = 'campaign_report_actions'
        constraints = [
            models.UniqueConstraint(
                fields=['campaign', 'question_text'],
                name='core_campaign_report_action_unique_question',
            ),
        ]


class CampaignReportSettings(TenantModel):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='report_settings',
    )
    reevaluate_months = models.PositiveSmallIntegerField(default=3)
    attachments = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'campaign_report_settings'
        constraints = [
            models.UniqueConstraint(
                fields=['campaign'],
                name='core_campaign_report_settings_unique_campaign',
            ),
        ]


class StandardActionPlan(TenantModel):
    step = models.PositiveSmallIntegerField()
    question_number = models.PositiveSmallIntegerField()
    question_text = models.TextField()
    actions = models.JSONField(default=list, blank=True)
    trigger_score_lt = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('4.30'))
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'standard_action_plans'
        ordering = ['step', 'question_number']
        unique_together = (('company', 'question_number'),)

    def __str__(self) -> str:
        return f'{self.question_number}. {self.question_text}'



class TechnicalResponsible(models.Model):
    name = models.CharField(max_length=150)
    education = models.CharField(max_length=255)
    registration = models.CharField(max_length=80)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'technical_responsibles'
        ordering = ['sort_order', 'name']

    def __str__(self) -> str:
        return self.name

class MoodType(TenantModel):
    label = models.CharField(max_length=80)
    emoji = models.CharField(max_length=32, default='🙂')
    sentiment = models.CharField(max_length=20)
    mood_score = models.PositiveSmallIntegerField(default=3)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'mood_types'
        ordering = ['label']
        unique_together = (('company', 'label'),)
        constraints = [
            models.CheckConstraint(
                condition=Q(mood_score__gte=1) & Q(mood_score__lte=5),
                name='core_mood_types_score_range',
            ),
        ]


class ComplaintType(TenantModel):
    label = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'complaint_types'
        ordering = ['label']
        unique_together = (('company', 'label'),)


class HelpRequest(TenantModel):
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Aberto'
        IN_PROGRESS = 'IN_PROGRESS', 'Em atendimento'
        RESOLVED = 'RESOLVED', 'Concluido'

    requester_name = models.CharField(max_length=150)
    department_name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    admin_notes = models.TextField(blank=True)
    totem = models.ForeignKey(
        'Totem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='help_requests',
    )

    class Meta:
        db_table = 'help_requests'
        ordering = ['-created_at']


class HelpRequestActionHistory(TenantModel):
    help_request = models.ForeignKey(
        HelpRequest,
        on_delete=models.CASCADE,
        related_name='action_histories',
    )
    status = models.CharField(max_length=20, choices=HelpRequest.Status.choices)
    admin_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='help_request_action_histories',
    )

    class Meta:
        db_table = 'help_request_action_histories'
        ordering = ['-created_at']


class AlertSetting(TenantModel):
    auto_alerts_enabled = models.BooleanField(default=True)
    analysis_window_days = models.PositiveSmallIntegerField(default=30)
    max_critical_complaints = models.PositiveIntegerField(default=5)
    max_negative_mood_percent = models.DecimalField(max_digits=5, decimal_places=2, default=35)
    max_open_help_requests = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'alert_settings'
        constraints = [
            models.UniqueConstraint(
                fields=['company'],
                name='core_alert_settings_one_per_company',
            ),
        ]


class AlertRecipient(TenantModel):
    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'alert_recipients'
        ordering = ['email']
        unique_together = (('company', 'email'),)


class Totem(TenantModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=80)
    location = models.CharField(max_length=180, blank=True)
    assessment_type = models.CharField(max_length=20, blank=True, default='setor')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'totems'
        ordering = ['name']
        unique_together = (('company', 'slug'),)

    def __str__(self) -> str:
        return self.name


class User(StandardPeriodModel):
    username = models.CharField(max_length=150)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    role = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta(StandardPeriodModel.Meta):
        db_table = 'users'
        ordering = ['full_name']
        unique_together = (('company', 'username'), ('company', 'email'))

    def __str__(self) -> str:
        return self.full_name


class MoodRecord(StandardPeriodModel):
    SENTIMENT_CHOICES = (
        ('very_bad', 'Muito ruim'),
        ('bad', 'Ruim'),
        ('neutral', 'Neutro'),
        ('good', 'Bom'),
        ('very_good', 'Muito bom'),
    )

    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES)
    mood_score = models.PositiveSmallIntegerField()
    channel = models.CharField(max_length=60, default='totem')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mood_records',
    )
    totem = models.ForeignKey(
        Totem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mood_records',
    )
    is_anonymous = models.BooleanField(default=True, editable=False)

    class Meta(StandardPeriodModel.Meta):
        db_table = 'mood_records'
        ordering = ['-record_date', '-created_at']
        constraints = StandardPeriodModel.Meta.constraints + [
            models.CheckConstraint(
                condition=Q(mood_score__gte=1) & Q(mood_score__lte=5),
                name='core_mood_records_score_range',
            ),
            models.CheckConstraint(
                condition=Q(is_anonymous=True),
                name='core_mood_records_anonymous_only',
            ),
        ]


class RiskIndicator(StandardPeriodModel):
    LEVEL_CHOICES = (
        ('low', 'Baixo'),
        ('medium', 'Medio'),
        ('high', 'Alto'),
        ('critical', 'Critico'),
    )

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    threshold = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta(StandardPeriodModel.Meta):
        db_table = 'risk_indicators'
        ordering = ['-record_date', '-created_at']
        unique_together = (('company', 'code', 'record_date'),)


class Complaint(StandardPeriodModel):
    CATEGORY_CHOICES = (
        ('assedio_moral', 'Assedio moral'),
        ('assedio_sexual', 'Assedio sexual'),
        ('discriminacao', 'Discriminacao'),
        ('conduta_antietica', 'Conduta antietica'),
        ('violencia_psicologica', 'Violencia psicologica'),
        ('other', 'Outros'),
        ('behavior', 'Comportamento'),
        ('workload', 'Carga de trabalho'),
    )
    STATUS_CHOICES = (
        ('RECEIVED', 'Recebido'),
        ('INVESTIGATING', 'Em apuração'),
        ('CLOSED', 'Encerrado'),
    )

    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    complaint_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RECEIVED')
    channel = models.CharField(max_length=60, default='totem')
    totem = models.ForeignKey(
        Totem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
    )
    occurrence_count = models.PositiveIntegerField(default=1)
    details = models.TextField(blank=True, null=True)
    is_anonymous = models.BooleanField(default=True, editable=False)

    class Meta(StandardPeriodModel.Meta):
        db_table = 'complaints'
        ordering = ['-record_date', '-created_at']
        constraints = StandardPeriodModel.Meta.constraints + [
            models.CheckConstraint(
                condition=Q(occurrence_count__gte=1),
                name='core_complaints_occurrence_count_min',
            ),
            models.CheckConstraint(
                condition=Q(is_anonymous=True),
                name='core_complaints_anonymous_only',
            ),
        ]


class ComplaintActionHistory(TenantModel):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='action_histories',
    )
    complaint_status = models.CharField(max_length=20, choices=Complaint.STATUS_CHOICES)
    action_note = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaint_action_histories',
    )

    class Meta:
        db_table = 'complaint_action_histories'
        ordering = ['-created_at']


class SupportAction(StandardPeriodModel):
    STATUS_CHOICES = (
        ('planned', 'Planejada'),
        ('in_progress', 'Em andamento'),
        ('done', 'Concluida'),
        ('canceled', 'Cancelada'),
    )

    action_type = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_actions',
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_support_actions',
    )
    due_date = models.DateField(null=True, blank=True)

    class Meta(StandardPeriodModel.Meta):
        db_table = 'support_actions'
        ordering = ['-record_date', '-created_at']


class Alert(StandardPeriodModel):
    ALERT_TYPE_CHOICES = (
        ('risk', 'Risco'),
        ('complaint', 'Queixa'),
        ('operational', 'Operacional'),
    )
    LEVEL_CHOICES = (
        ('low', 'Baixo'),
        ('medium', 'Medio'),
        ('high', 'Alto'),
        ('critical', 'Critico'),
    )
    STATUS_CHOICES = (
        ('open', 'Aberto'),
        ('acknowledged', 'Reconhecido'),
        ('closed', 'Fechado'),
    )

    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    risk_indicator = models.ForeignKey(
        RiskIndicator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts',
    )
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts',
    )

    class Meta(StandardPeriodModel.Meta):
        db_table = 'alerts'
        ordering = ['-record_date', '-created_at']


class Report(StandardPeriodModel):
    REPORT_TEMPLATE_CHOICES = (
        ('technical', 'RELATORIO TECNICO DE SAUDE MENTAL ORGANIZACIONAL'),
        ('other', 'Outro relatorio'),
    )
    REPORT_TYPE_CHOICES = (
        ('daily', 'Diario'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensal'),
        ('custom', 'Personalizado'),
    )
    STATUS_CHOICES = (
        ('queued', 'Em fila'),
        ('processing', 'Processando'),
        ('ready', 'Pronto'),
        ('failed', 'Falhou'),
    )

    report_template = models.CharField(
        max_length=30,
        choices=REPORT_TEMPLATE_CHOICES,
        default='technical',
    )
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    title = models.CharField(max_length=255)
    generated_at = models.DateTimeField(null=True, blank=True)
    storage_path = models.CharField(max_length=500, null=True, blank=True)
    mood_analysis = models.TextField(blank=True, default='')
    complaint_analysis = models.TextField(blank=True, default='')
    technical_recommendations = models.TextField(blank=True, default='')

    class Meta(StandardPeriodModel.Meta):
        db_table = 'reports'
        ordering = ['-record_date', '-created_at']
