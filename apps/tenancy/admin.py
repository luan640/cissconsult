from django.contrib import admin

from .models import Company, CompanyMembership, Consultancy, ConsultancyMembership


@admin.register(Consultancy)
class ConsultancyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'consultancy', 'slug', 'is_active')
    list_filter = ('consultancy', 'is_active')
    search_fields = ('name', 'slug', 'consultancy__name')


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company', 'role', 'is_default', 'is_active')
    list_filter = ('company', 'is_default', 'is_active')
    search_fields = ('user__username', 'user__email', 'company__name')


@admin.register(ConsultancyMembership)
class ConsultancyMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'consultancy', 'role', 'is_default', 'is_active')
    list_filter = ('consultancy', 'is_default', 'is_active')
    search_fields = ('user__username', 'user__email', 'consultancy__name')
