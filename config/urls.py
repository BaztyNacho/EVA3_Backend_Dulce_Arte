"""
Rutas (URLs) principales del proyecto Dulce Arte.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
]

# En desarrollo, Django sirve las imágenes subidas (firmas, comprobantes, productos).
# En producción (AWS) esto lo hará Nginx.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)