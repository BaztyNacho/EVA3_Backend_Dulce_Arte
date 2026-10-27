"""
Rutas de la API REST de Dulce Arte.
Todas quedan bajo /api/ (ver config/urls.py).
"""

from rest_framework.routers import DefaultRouter

from despachos.api import DespachoViewSet, RutaViewSet
from inventario.api import (
    InsumoViewSet,
    MovimientoInsumoViewSet,
    OpcionPersonalizacionViewSet,
    ProductoViewSet,
)
from pedidos.api import ClienteViewSet, PedidoViewSet

router = DefaultRouter()

# Inventario
router.register('insumos', InsumoViewSet, basename='insumo')
router.register('productos', ProductoViewSet, basename='producto')
router.register('opciones-personalizacion', OpcionPersonalizacionViewSet, basename='opcion')
router.register('movimientos-insumo', MovimientoInsumoViewSet, basename='movimiento')

# Pedidos
router.register('clientes', ClienteViewSet, basename='cliente')
router.register('pedidos', PedidoViewSet, basename='pedido')

# Despachos
router.register('rutas', RutaViewSet, basename='ruta')
router.register('despachos', DespachoViewSet, basename='despacho')

urlpatterns = router.urls
