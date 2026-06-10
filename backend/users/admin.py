from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.html import format_html

from unfold.admin import ModelAdmin

from .models import User


class EmailUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "username")


class EmailUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(ModelAdmin, BaseUserAdmin):
    form = EmailUserChangeForm
    add_form = EmailUserCreationForm

    _BADGE = (
        "display:inline-block;padding:2px 8px;border-radius:4px;"
        "font-size:11px;font-weight:600;letter-spacing:.03em;"
    )

    list_display = ("email", "username", "is_verified", "is_staff", "date_joined", "email_verified_badge")
    search_fields = ("email", "username")
    ordering = ("-date_joined",)

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2"),
        }),
    )

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "avatar", "bio")}),
        ("Permissions", {"fields": ("is_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )

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
