from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import Classroom, Membership, Organization, OrgMember, ShadowSet


@admin.register(Classroom)
class ClassroomAdmin(ModelAdmin):
    list_display = ("name", "organization", "owner", "level", "student_count", "join_code", "archived", "created_at")
    list_filter = ("archived", "level", "organization")
    search_fields = ("name", "owner__email", "join_code", "organization__name")
    list_select_related = ("owner", "organization")
    raw_id_fields = ("owner", "organization")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Classroom]:
        return super().get_queryset(request).annotate(student_total=Count("memberships", distinct=True))

    @display(description="Students", ordering="student_total")
    def student_count(self, obj: Classroom) -> int:
        return obj.student_total


@admin.register(Membership)
class MembershipAdmin(ModelAdmin):
    list_display = ("classroom", "user", "joined_at")
    search_fields = ("classroom__name", "user__email")
    list_select_related = ("classroom", "user")
    raw_id_fields = ("classroom", "user")


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ("name", "slug", "owner", "class_count", "web_search_enabled", "created_at")
    list_filter = ("web_search_enabled",)
    search_fields = ("name", "slug", "owner__email")
    list_select_related = ("owner",)
    raw_id_fields = ("owner",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Organization]:
        return super().get_queryset(request).annotate(class_total=Count("classrooms", distinct=True))

    @display(description="Classes", ordering="class_total")
    def class_count(self, obj: Organization) -> int:
        return obj.class_total


@admin.register(OrgMember)
class OrgMemberAdmin(ModelAdmin):
    list_display = ("organization", "user", "role", "joined_at")
    list_filter = ("role",)
    search_fields = ("organization__name", "user__email")
    list_select_related = ("organization", "user")
    raw_id_fields = ("organization", "user")


@admin.register(ShadowSet)
class ShadowSetAdmin(ModelAdmin):
    list_display = ("classroom", "created_by", "language", "target", "status_badge", "created_at")
    list_filter = ("status", "language")
    search_fields = ("classroom__name", "prompt")
    list_select_related = ("classroom", "created_by")
    readonly_fields = ("classroom", "created_by", "prompt", "language", "target", "status", "error", "created_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @display(
        description="Status",
        ordering="status",
        label={"pending": "", "running": "info", "done": "success", "failed": "danger"},
    )
    def status_badge(self, obj: ShadowSet) -> str:
        return obj.status
