"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("medecin/", include("cabinet.doctor_urls")),
    path("secretaire/", include("cabinet.secretary_urls")),
    path("patients/", include("patients.urls")),
    path("", include("accounts.urls")),
]

# En DEBUG : sert /static/ depuis tous les STATICFILES_DIRS + static/ des apps (ex. accounts/static/…)
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
