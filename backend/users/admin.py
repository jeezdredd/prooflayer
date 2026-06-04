from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from unfold.admin import ModelAdmin

from .models import User


@admin.register(User)
class UserAdmin(ModelAdmin, BaseUserAdmin):
    _BADGE = (
        "display:inline-block;padding:2px 8px;border-radius:4px;"
        "font-size:11px;font-weight:600;letter-spacing:.03em;"
    )

    list_display = BaseUserAdmin.list_display + ("email_verified_badge",)

    @admin.display(description="Email verified", ordering="is_verified")
    def email_verified_badge(self, obj):
        if obj.is_verified:
            return format_html(
                '<span style="{}background:#14532d;color:#86efac">VERIFIED</span>',
                self._BADGE,
            )
        return format_html(
            '<span style="{}background:#7f1d1d;color:#fca5a5">UNVERIFIED</span>',
            self._BADGE,
        )
