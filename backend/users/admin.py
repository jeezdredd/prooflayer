from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.html import format_html

from unfold.admin import ModelAdmin
from unfold.decorators import action

from api.changelog import draft_digest, pending_entries
from common.admin_tools import SuperuserActionsAdmin

from .models import ApiKey, EmailLog, ProductUpdate, User
from .tasks import send_product_update, send_product_update_to, update_audience


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
        ("Age and terms", {"fields": ("is_adult", "age_confirmed_at", "terms_version", "terms_accepted_at")}),
        ("Email", {"fields": ("language", "email_updates", "allow_training", "training_consent_at")}),
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


@admin.register(EmailLog)
class EmailLogAdmin(ModelAdmin):
    list_display = ("created_at", "to_email", "kind", "status", "backend")
    list_filter = ("status", "kind", "backend")
    search_fields = ("to_email",)
    readonly_fields = ("created_at", "to_email", "kind", "subject", "backend", "status", "error", "user")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ApiKey)
class ApiKeyAdmin(ModelAdmin):
    list_display = ("prefix", "name", "user", "created_at", "last_used_at", "revoked_at", "last_webhook_status")
    list_filter = ("revoked_at",)
    search_fields = ("prefix", "name", "user__email")
    readonly_fields = ("prefix", "key_hash", "webhook_secret", "created_at", "last_used_at", "last_webhook_at", "last_webhook_status")
    exclude = ()

    def has_add_permission(self, request):
        return False


@admin.register(ProductUpdate)
class ProductUpdateAdmin(SuperuserActionsAdmin):
    list_display = ("title_en", "status", "created_at", "sent_at", "recipients")
    list_filter = ("status",)
    readonly_fields = ("status", "created_at", "sent_at", "recipients")
    actions = ("send_test_to_me", "send_to_subscribers")
    actions_list = ["draft_from_changelog"]

    @action(description="Draft digest from changelog", icon="auto_awesome", permissions=["superuser"], url_path="draft-digest")
    def draft_from_changelog(self, request):
        if pending_entries().count() == 0:
            self.message_user(request, "No new changelog entries since the last digest.", messages.WARNING)
            return self.back_to_changelist()
        update = draft_digest()
        self.message_user(request, f"Drafted “{update}” from {update.changelog_entries.count()} changelog entries. Review it, send a test, then send.", messages.SUCCESS)
        return self.back_to_changelist()
    fieldsets = (
        ("English", {"fields": ("title_en", "summary_en", "body_en", "cta_label_en")}),
        ("Русский", {"fields": ("title_ru", "summary_ru", "body_ru", "cta_label_ru")}),
        ("Button and delivery", {"fields": ("cta_url", "status", "created_at", "sent_at", "recipients")}),
    )

    @admin.action(description="Send a test copy to me")
    def send_test_to_me(self, request, queryset):
        for update in queryset:
            send_product_update_to(update, request.user)
        self.message_user(request, f"Sent {queryset.count()} test email(s) to {request.user.email} in {request.user.language.upper()}.")

    @admin.action(description="Send to all subscribers")
    def send_to_subscribers(self, request, queryset):
        for update in queryset:
            if update.status == ProductUpdate.Status.SENT:
                self.message_user(request, f"“{update}” was already sent.", messages.WARNING)
                continue
            audience = update_audience(update).count()
            send_product_update.delay(update.pk)
            self.message_user(request, f"“{update}” is going out to {audience} subscribers.")
