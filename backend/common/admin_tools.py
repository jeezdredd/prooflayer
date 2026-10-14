from collections.abc import Iterable
from typing import Any

from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from unfold.admin import ModelAdmin


class SuperuserActionsAdmin(ModelAdmin):
    def has_superuser_permission(self, request: HttpRequest, object_id: Any = None) -> bool:
        return bool(request.user.is_active and request.user.is_superuser)

    def changelist_url(self) -> str:
        opts = self.model._meta
        return reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")

    def back_to_changelist(self) -> HttpResponseRedirect:
        return redirect(self.changelist_url())

    def confirm_action(
        self,
        request: HttpRequest,
        *,
        title: str,
        message: str,
        button: str,
        details: Iterable[dict[str, Any]] = (),
        danger: bool = False,
    ) -> TemplateResponse:
        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "message": message,
            "button": button,
            "button_variant": "danger" if danger else "primary",
            "details": list(details),
            "cancel_url": self.changelist_url(),
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/confirm_action.html", context)
