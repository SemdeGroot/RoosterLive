from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.views.twofa import CustomLoginView, CustomSetupView, CustomQRGeneratorView

two_factor_patterns = [
    path("account/login/", CustomLoginView.as_view(), name="login"),
    path("account/two_factor/setup/", CustomSetupView.as_view(), name="setup"),
    path("account/two_factor/qrcode/", CustomQRGeneratorView.as_view(), name="qr"),
]

urlpatterns = [
    path("", include("core.urls")),
    path("", include((two_factor_patterns, "two_factor"), namespace="two_factor")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
