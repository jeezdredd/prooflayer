from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Classroom, Membership


@admin.register(Classroom)
class ClassroomAdmin(ModelAdmin):
    list_display = ("name", "owner", "join_code", "archived", "created_at")
    list_filter = ("archived",)
    search_fields = ("name", "owner__email", "join_code")


@admin.register(Membership)
class MembershipAdmin(ModelAdmin):
    list_display = ("classroom", "user", "joined_at")
    search_fields = ("classroom__name", "user__email")
