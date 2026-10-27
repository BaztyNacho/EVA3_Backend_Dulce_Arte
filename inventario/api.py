"""
API REST de INVENTARIO (vistas de Django REST Framework).
"""

from django.db.models import F
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from pedidos.permisos import (
    EsAdministrador,
    PermisosDelModelo,
    ProtegidoContraBorradoMixin,
    es_administrador,
)
from pedidos.services import ReglaNegocioError

from .models import Insumo, MovimientoInsumo, OpcionPersonalizacion, Producto
from .serializers import (
    InsumoSerializer,
    MovimientoInsumoSerializer,
    OpcionPersonalizacionSerializer,
    ProductoSerializer,
)
from .services import registrar_movimiento


class InsumoViewSet(ProtegidoContraBorradoMixin, viewsets.ModelViewSet):
    """Insumos de bodega. Solo Administrador."""

    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer
    permission_classes = [EsAdministrador]

    @action(detail=False, methods=['get'], url_path='stock-bajo')
    def stock_bajo(self, request):
        """Insumos que llegaron a su stock mínimo (alerta)."""
        insumos = self.get_queryset().filter(activo=True, stock_actual__lte=F('stock_minimo'))
        return Response(self.get_serializer(insumos, many=True).data)


class ProductoViewSet(ProtegidoContraBorradoMixin, viewsets.ModelViewSet):
    """Catálogo de productos. Ventas solo puede verlos (y solo los activos)."""

    serializer_class = ProductoSerializer
    permission_classes = [PermisosDelModelo]
    queryset = Producto.objects.prefetch_related('receta__insumo')

    def get_queryset(self):
        queryset = super().get_queryset()
        if not es_administrador(self.request.user):
            queryset = queryset.filter(activo=True)
        return queryset


class OpcionPersonalizacionViewSet(ProtegidoContraBorradoMixin, viewsets.ModelViewSet):
    """Opciones de personalización. Ventas solo puede verlas (y solo las activas)."""

    serializer_class = OpcionPersonalizacionSerializer
    permission_classes = [PermisosDelModelo]
    queryset = OpcionPersonalizacion.objects.select_related('insumo')

    def get_queryset(self):
        queryset = super().get_queryset()
        if not es_administrador(self.request.user):
            queryset = queryset.filter(activo=True)
        return queryset


class MovimientoInsumoViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Movimientos de bodega (trazabilidad). Se pueden crear y consultar,
    pero no modificar ni borrar. Solo Administrador.
    Filtro opcional: ?insumo=<id>
    """

    serializer_class = MovimientoInsumoSerializer
    permission_classes = [EsAdministrador]
    queryset = MovimientoInsumo.objects.select_related('insumo', 'usuario')

    def get_queryset(self):
        queryset = super().get_queryset()
        insumo = self.request.query_params.get('insumo')
        if insumo:
            queryset = queryset.filter(insumo_id=insumo)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        try:
            movimiento = registrar_movimiento(
                insumo=datos['insumo'],
                tipo=datos['tipo'],
                cantidad=datos['cantidad'],
                usuario=request.user,
                motivo=datos.get('motivo', ''),
            )
        except ReglaNegocioError as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(movimiento).data, status=status.HTTP_201_CREATED)
