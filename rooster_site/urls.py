from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache

from core.views.twofa import CustomLoginView, CustomSetupView, CustomQRGeneratorView

two_factor_patterns = [
    path("account/login/", CustomLoginView.as_view(), name="login"),
    path("account/two_factor/setup/", CustomSetupView.as_view(), name="setup"),
    path("account/two_factor/qrcode/", CustomQRGeneratorView.as_view(), name="qr"),
]

urlpatterns = [
    path("", include("core.urls")),
    path("", include((two_factor_patterns, "two_factor"), namespace="two_factor")),

        path(
        "manifest.json",
        never_cache(TemplateView.as_view(
            template_name="manifest.json",
            content_type="application/manifest+json",
        )),
        name="manifest.json",
    ),


path(
    "service_worker.v20.js",
    never_cache(
        TemplateView.as_view(
            template_name="service_worker.v20.js",
            content_type="application/javascript",
        )
    ),
    name="service_worker.v20",
),
]

# Static alleen in DEBUG via Django (prod doet static via WhiteNoise)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)