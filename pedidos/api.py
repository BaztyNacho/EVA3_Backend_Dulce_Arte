"""
API REST de PEDIDOS (vistas de Django REST Framework).
"""

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from inventario.models import Insumo

from .models import Cliente, Pedido
from .permisos import EsAdministrador, PermisosDelModelo, ProtegidoContraBorradoMixin
from .serializers import (
    ClienteSerializer,
    ImagenReferenciaSerializer,
    MotivoSerializer,
    PedidoKanbanSerializer,
    PedidoSerializer,
)
from .services import (
    ReglaNegocioError,
    avanzar_estado,
    calcular_requerimientos,
    cancelar_pedido,
    confirmar_cotizacion,
    rechazar_control_calidad,
)


class ClienteViewSet(ProtegidoContraBorradoMixin, viewsets.ModelViewSet):
    """
    Clientes de la pastelería.
    Búsqueda opcional: ?q=<nombre o teléfono>
    """

    serializer_class = ClienteSerializer
    permission_classes = [PermisosDelModelo]
    queryset = Cliente.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        texto = self.request.query_params.get('q')
        if texto:
            queryset = queryset.filter(Q(nombre__icontains=texto) | Q(telefono__icontains=texto))
        return queryset


class PedidoViewSet(viewsets.ModelViewSet):
    """
    Cotizaciones y pedidos.
    Filtros opcionales: ?estado=recibido,listo  ?cliente=<id>  ?tipo_entrega=despacho
    """

    serializer_class = PedidoSerializer
    permission_classes = [PermisosDelModelo]
    queryset = (
        Pedido.objects.select_related('cliente', 'creado_por')
        .prefetch_related(
            'detalles__producto',
            'detalles__personalizaciones__opcion',
            'historial__usuario',
        )
        .order_by('-creado_en')
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        parametros = self.request.query_params
        if parametros.get('estado'):
            queryset = queryset.filter(estado__in=parametros['estado'].split(','))
        if parametros.get('cliente'):
            queryset = queryset.filter(cliente_id=parametros['cliente'])
        if parametros.get('tipo_entrega'):
            queryset = queryset.filter(tipo_entrega=parametros['tipo_entrega'])
        return queryset

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    def destroy(self, request, *args, **kwargs):
        pedido = self.get_object()
        if pedido.estado != Pedido.Estado.COTIZACION:
            return Response(
                {'detail': 'Solo se pueden eliminar cotizaciones. Un pedido confirmado se cancela.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    # ---------------------------------------------------------------
    # Acciones de negocio (usan pedidos/services.py)
    # ---------------------------------------------------------------
    def _ejecutar(self, funcion, *args):
        pedido = self.get_object()
        try:
            funcion(pedido, self.request.user, *args)
        except ReglaNegocioError as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        pedido = self.get_queryset().get(pk=pedido.pk)
        return Response(PedidoSerializer(pedido, context=self.get_serializer_context()).data)

    @extend_schema(request=None, responses=PedidoSerializer)
    @action(detail=True, methods=['post'])
    def confirmar(self, request, pk=None):
        """Confirma la cotización: verifica stock, descuenta insumos y la envía a cocina."""
        return self._ejecutar(confirmar_cotizacion)

    @extend_schema(request=None, responses=PedidoSerializer)
    @action(detail=True, methods=['post'], permission_classes=[EsAdministrador])
    def avanzar(self, request, pk=None):
        """Mueve el pedido a la siguiente columna del Kanban."""
        return self._ejecutar(avanzar_estado)

    @extend_schema(request=MotivoSerializer, responses=PedidoSerializer)
    @action(detail=True, methods=['post'], url_path='rechazar-calidad', permission_classes=[EsAdministrador])
    def rechazar_calidad(self, request, pk=None):
        """Rechaza en Control de Calidad: el pedido vuelve a En Preparación."""
        motivo = MotivoSerializer(data=request.data)
        motivo.is_valid(raise_exception=True)
        return self._ejecutar(rechazar_control_calidad, motivo.validated_data.get('motivo', ''))

    @extend_schema(request=MotivoSerializer, responses=PedidoSerializer)
    @action(detail=True, methods=['post'], permission_classes=[EsAdministrador])
    def cancelar(self, request, pk=None):
        """Cancela el pedido (devuelve insumos si aún no se empezó a preparar)."""
        motivo = MotivoSerializer(data=request.data)
        motivo.is_valid(raise_exception=True)
        return self._ejecutar(cancelar_pedido, motivo.validated_data.get('motivo', ''))

    @action(detail=True, methods=['get'])
    def disponibilidad(self, request, pk=None):
        """Insumos que necesita el pedido y si hay stock suficiente de cada uno."""
        pedido = self.get_object()
        requerimientos = calcular_requerimientos(pedido)
        insumos = Insumo.objects.in_bulk(list(requerimientos))
        detalle = [
            {
                'insumo': insumos[insumo_id].nombre,
                'unidad': insumos[insumo_id].unidad,
                'necesario': cantidad,
                'disponible': insumos[insumo_id].stock_actual,
                'suficiente': insumos[insumo_id].stock_actual >= cantidad,
            }
            for insumo_id, cantidad in requerimientos.items()
        ]
        return Response({
            'pedido': pedido.pk,
            'hay_stock_suficiente': all(item['suficiente'] for item in detalle),
            'insumos': detalle,
        })

    @extend_schema(request=ImagenReferenciaSerializer, responses=PedidoSerializer)
    @action(
        detail=True,
        methods=['post'],
        url_path='imagen-referencia',
        parser_classes=[MultiPartParser, FormParser],
    )
    def imagen_referencia(self, request, pk=None):
        """Sube la imagen de referencia del diseño (solo en cotizaciones)."""
        pedido = self.get_object()
        if pedido.estado != Pedido.Estado.COTIZACION:
            return Response(
                {'detail': 'Solo se puede cambiar la imagen de una cotización.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        datos = ImagenReferenciaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        pedido.imagen_referencia = datos.validated_data['imagen_referencia']
        pedido.save(update_fields=['imagen_referencia', 'actualizado_en'])
        return Response(PedidoSerializer(pedido, context=self.get_serializer_context()).data)

    @extend_schema(responses=PedidoKanbanSerializer(many=True))
    @action(detail=False, methods=['get'], permission_classes=[EsAdministrador])
    def kanban(self, request):
        """Pedidos agrupados por columna del tablero de cocina."""
        pedidos = (
            Pedido.objects.filter(estado__in=Pedido.ESTADOS_KANBAN)
            .select_related('cliente')
            .prefetch_related('detalles__producto')
            .order_by('fecha_entrega')
        )
        columnas = []
        for estado in Pedido.ESTADOS_KANBAN:
            tarjetas = [p for p in pedidos if p.estado == estado]
            columnas.append({
                'estado': estado,
                'titulo': Pedido.Estado(estado).label,
                'pedidos': PedidoKanbanSerializer(tarjetas, many=True).data,
            })
        return Response(columnas)
