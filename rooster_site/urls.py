from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve

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

# Media: ook bij DEBUG=False via Django serveren (zolang SERVE_MEDIA_LOCALLY=True)
if settings.SERVE_MEDIA_LOCALLY:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]

# Static alleen in DEBUG via Django (prod doet static via WhiteNoise)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]