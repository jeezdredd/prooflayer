from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Vote


@admin.register(Vote)
class VoteAdmin(ModelAdmin):
    list_display = ("id", "user", "submission", "value", "created_at")
    list_filter = ("value",)
