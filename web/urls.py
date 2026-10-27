"""
Rutas de la interfaz web.
"""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path(
        'ingresar/',
        auth_views.LoginView.as_view(template_name='web/login.html', redirect_authenticated_user=True),
        name='login',
    ),
    path('salir/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.inicio, name='inicio'),
    path('pedidos/', views.pedidos_lista, name='pedidos_lista'),
    path('pedidos/nuevo/', views.pedido_nuevo, name='pedido_nuevo'),
    path('pedidos/<int:pk>/', views.pedido_detalle, name='pedido_detalle'),
    # Solo Atención y Ventas
    path('catalogo/', views.catalogo, name='catalogo'),
    # Solo Administrador
    path('cocina/', views.kanban, name='kanban'),
    path('bodega/', views.bodega, name='bodega'),
    path('despachos/', views.despachos, name='despachos'),
    path('despachos/<int:pk>/entregar/', views.despacho_entrega, name='despacho_entrega'),
]
