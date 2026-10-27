"""
Rutas (URLs) principales del proyecto Dulce Arte.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Textos del panel de administración
admin.site.site_header = 'Dulce Arte · Administración'
admin.site.site_title = 'Dulce Arte'
admin.site.index_title = 'Panel de gestión de la pastelería'

urlpatterns = [
    path('admin/', admin.site.urls),
    # API REST
    path('api/', include('config.api')),
    path('api-auth/', include('rest_framework.urls')),  # login para la API navegable
    # Documentación de la API (Swagger)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# En desarrollo, Django sirve las imágenes subidas (firmas, comprobantes, productos).
# En producción (AWS) esto lo hará Nginx.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
