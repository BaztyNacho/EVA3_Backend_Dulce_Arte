"""
API REST de DESPACHOS (vistas de Django REST Framework). Solo Administrador.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from pedidos.permisos import EsAdministrador, ProtegidoContraBorradoMixin
from pedidos.services import ReglaNegocioError

from .models import Despacho, Ruta
from .serializers import ConfirmarEntregaSerializer, DespachoSerializer, RutaSerializer
from .services import confirmar_entrega


class RutaViewSet(ProtegidoContraBorradoMixin, viewsets.ModelViewSet):
    """Rutas de reparto con sus despachos."""

    serializer_class = RutaSerializer
    permission_classes = [EsAdministrador]
    queryset = Ruta.objects.select_related('responsable').prefetch_related(
        'despachos__pedido__cliente'
    )


class DespachoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Despachos. Se crean automáticamente cuando un pedido con despacho pasa de "Listo".
    Filtros opcionales: ?estado=pendiente,en_camino  ?ruta=<id>
    """

    serializer_class = DespachoSerializer
    permission_classes = [EsAdministrador]
    queryset = Despacho.objects.select_related('pedido__cliente', 'ruta')

    def get_queryset(self):
        queryset = super().get_queryset()
        parametros = self.request.query_params
        if parametros.get('estado'):
            queryset = queryset.filter(estado__in=parametros['estado'].split(','))
        if parametros.get('ruta'):
            queryset = queryset.filter(ruta_id=parametros['ruta'])
        return queryset

    @extend_schema(request=ConfirmarEntregaSerializer, responses=DespachoSerializer)
    @action(
        detail=True,
        methods=['post'],
        url_path='confirmar-entrega',
        parser_classes=[JSONParser, MultiPartParser, FormParser],
    )
    def confirmar_entrega(self, request, pk=None):
        """
        Confirma la entrega con firma digital (imagen en base64 desde el canvas)
        y/o foto del comprobante. El pedido pasa a "Entregado".
        """
        despacho = self.get_object()
        datos = ConfirmarEntregaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        try:
            despacho = confirmar_entrega(despacho, request.user, **datos.validated_data)
        except ReglaNegocioError as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(despacho).data)
