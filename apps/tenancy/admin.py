from django.contrib import admin

from .models import Company, CompanyMembership


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company', 'role', 'is_default', 'is_active')
    list_filter = ('company', 'is_default', 'is_active')
    search_fields = ('user__username', 'user__email', 'company__name')
