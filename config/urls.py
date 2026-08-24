from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("admin/", admin.site.urls), path("", include("ems.urls"))]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "ems.views.error_403"
handler404 = "ems.views.error_404"
handler500 = "ems.views.error_500"
handler400 = "ems.views.error_400"
