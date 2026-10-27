"""
Serializers de DESPACHOS.
"""

import base64
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers

from .models import Despacho, Ruta


class FirmaBase64Field(serializers.ImageField):
    """
    Recibe la firma dibujada en el navegador (canvas) como texto
    "data:image/png;base64,...." y la convierte en un archivo de imagen.
    También acepta un archivo de imagen normal.
    """

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            try:
                formato, contenido = data.split(';base64,')
                extension = formato.split('/')[-1]
                data = ContentFile(base64.b64decode(contenido), name=f'firma_{uuid.uuid4().hex[:10]}.{extension}')
            except (ValueError, TypeError):
                raise serializers.ValidationError('La firma no tiene un formato válido.')
        return super().to_internal_value(data)


class DespachoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    cliente_nombre = serializers.CharField(source='pedido.cliente.nombre', read_only=True)
    cliente_telefono = serializers.CharField(source='pedido.cliente.telefono', read_only=True)
    direccion_entrega = serializers.CharField(source='pedido.direccion_entrega', read_only=True)
    fecha_entrega_programada = serializers.DateTimeField(source='pedido.fecha_entrega', read_only=True)
    ruta_nombre = serializers.CharField(source='ruta.nombre', read_only=True, default=None)

    class Meta:
        model = Despacho
        fields = [
            'id',
            'pedido',
            'cliente_nombre',
            'cliente_telefono',
            'direccion_entrega',
            'fecha_entrega_programada',
            'ruta',
            'ruta_nombre',
            'orden',
            'estado',
            'estado_display',
            'nombre_receptor',
            'firma',
            'comprobante',
            'fecha_entrega_real',
            'observaciones',
        ]
        read_only_fields = [
            'pedido',
            'nombre_receptor',
            'firma',
            'comprobante',
            'fecha_entrega_real',
        ]

    def validate_estado(self, estado):
        if estado == Despacho.Estado.ENTREGADO:
            raise serializers.ValidationError(
                'Para marcar como entregado usa la acción "confirmar-entrega" (exige firma o comprobante).'
            )
        if self.instance and self.instance.estado == Despacho.Estado.ENTREGADO:
            raise serializers.ValidationError('Un despacho entregado no puede cambiar de estado.')
        return estado


class ConfirmarEntregaSerializer(serializers.Serializer):
    nombre_receptor = serializers.CharField(max_length=150)
    firma = FirmaBase64Field(required=False)
    comprobante = serializers.ImageField(required=False)
    observaciones = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('firma') and not attrs.get('comprobante'):
            raise serializers.ValidationError(
                'Se requiere la firma digital o la foto del comprobante.'
            )
        return attrs


class RutaSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    responsable_nombre = serializers.CharField(source='responsable.username', read_only=True, default=None)
    despachos = DespachoSerializer(many=True, read_only=True)

    class Meta:
        model = Ruta
        fields = [
            'id',
            'nombre',
            'fecha',
            'responsable',
            'responsable_nombre',
            'estado',
            'estado_display',
            'observaciones',
            'despachos',
        ]
