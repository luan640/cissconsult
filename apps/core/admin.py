from django.contrib import admin

from .models import (
    Alert,
    Campaign,
    Complaint,
    Department,
    GHE,
    MoodRecord,
    Report,
    RiskIndicator,
    SupportAction,
    Totem,
    User,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'company', 'is_active')
    search_fields = ('name',)
    list_filter = ('company', 'is_active')

    def get_queryset(self, request):
        return Department.all_objects.all()


@admin.register(GHE)
class GHEAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'company', 'is_active')
    search_fields = ('name',)
    list_filter = ('company', 'is_active')

    def get_queryset(self, request):
        return GHE.all_objects.all()


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'company', 'start_date', 'end_date', 'status', 'created_by', 'created_at')
    search_fields = ('title', 'created_by__username', 'created_by__email')
    list_filter = ('company', 'status', 'start_date', 'end_date')

    def get_queryset(self, request):
        return Campaign.all_objects.all()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'full_name', 'email', 'company', 'is_active')
    list_filter = ('company', 'is_active', 'record_date')
    search_fields = ('username', 'full_name', 'email')

    def get_queryset(self, request):
        return User.all_objects.all()


@admin.register(MoodRecord)
class MoodRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'totem', 'record_date', 'sentiment', 'mood_score', 'channel')
    list_filter = ('company', 'totem', 'record_date', 'sentiment', 'channel')

    def get_queryset(self, request):
        return MoodRecord.all_objects.all()


@admin.register(RiskIndicator)
class RiskIndicatorAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'record_date', 'code', 'name', 'level', 'value')
    list_filter = ('company', 'record_date', 'level', 'is_active')
    search_fields = ('code', 'name')

    def get_queryset(self, request):
        return RiskIndicator.all_objects.all()


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'totem', 'record_date', 'category', 'channel')
    list_filter = ('company', 'totem', 'record_date', 'category')

    def get_queryset(self, request):
        return Complaint.all_objects.all()


@admin.register(SupportAction)
class SupportActionAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'record_date', 'action_type', 'status', 'owner')
    list_filter = ('company', 'record_date', 'status')
    search_fields = ('action_type',)

    def get_queryset(self, request):
        return SupportAction.all_objects.all()


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'record_date', 'alert_type', 'level', 'status')
    list_filter = ('company', 'record_date', 'alert_type', 'level', 'status')

    def get_queryset(self, request):
        return Alert.all_objects.all()


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'record_date', 'report_template', 'report_type', 'status', 'generated_at')
    list_filter = ('company', 'record_date', 'report_template', 'report_type', 'status')
    search_fields = ('title',)

    def get_queryset(self, request):
        return Report.all_objects.all()


@admin.register(Totem)
class TotemAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'company', 'location', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('name', 'slug', 'location')

    def get_queryset(self, request):
        return Totem.all_objects.all()
