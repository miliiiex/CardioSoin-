from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import EmailVerificationCode, Medecin, Secretaire, User


class AppUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


class AppUserCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AppUserChangeForm
    add_form = AppUserCreationForm

    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "role",
        "is_active",
    )
    list_filter = (*BaseUserAdmin.list_filter, "role")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email", "role")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(Medecin)
class MedecinAdmin(admin.ModelAdmin):
    list_display = ("user", "specialite", "qualification_display", "numero_ordre", "telephone", "cin")
    search_fields = ("user__username", "user__first_name", "user__last_name", "specialite")
    autocomplete_fields = ("user",)


@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ("email", "purpose", "created_at", "expires_at", "used_at", "attempts")
    list_filter = ("purpose", "used_at")
    search_fields = ("email",)
    readonly_fields = ("code_hash", "created_at")


@admin.register(Secretaire)
class SecretaireAdmin(admin.ModelAdmin):
    list_display = ("user", "telephone", "salaire", "cin")
