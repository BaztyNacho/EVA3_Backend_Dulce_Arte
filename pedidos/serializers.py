"""
Serializers de PEDIDOS.

El PedidoSerializer permite crear una cotización completa en una sola petición:
cliente + datos de entrega + productos + personalizaciones.
"""

import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Cliente, DetallePedido, HistorialEstado, Pedido, PersonalizacionDetalle
from .services import registrar_cambio


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['id', 'nombre', 'telefono', 'email', 'direccion', 'creado_en']
        read_only_fields = ['creado_en']


class PersonalizacionSerializer(serializers.ModelSerializer):
    opcion_nombre = serializers.CharField(source='opcion.nombre', read_only=True)
    precio_adicional = serializers.IntegerField(read_only=True)

    class Meta:
        model = PersonalizacionDetalle
        fields = ['opcion', 'opcion_nombre', 'porciones', 'precio_adicional']

    def validate_porciones(self, valor):
        if valor == 0:
            raise serializers.ValidationError('Las porciones no pueden ser 0.')
        return valor

    def validate_opcion(self, opcion):
        if not opcion.activo:
            raise serializers.ValidationError(f'La opción "{opcion.nombre}" no está disponible.')
        return opcion


class DetallePedidoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    personalizaciones = PersonalizacionSerializer(many=True, required=False)
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = DetallePedido
        fields = [
            'id',
            'producto',
            'producto_nombre',
            'cantidad',
            'precio_unitario',
            'comentario',
            'personalizaciones',
            'subtotal',
        ]
        read_only_fields = ['precio_unitario']

    def validate_producto(self, producto):
        if not producto.activo:
            raise serializers.ValidationError(f'El producto "{producto.nombre}" no está disponible.')
        return producto

    def validate_personalizaciones(self, personalizaciones):
        opciones = [p['opcion'].pk for p in personalizaciones]
        if len(opciones) != len(set(opciones)):
            raise serializers.ValidationError('No repitas la misma opción en un producto.')
        return personalizaciones


class HistorialEstadoSerializer(serializers.ModelSerializer):
    estado_anterior_display = serializers.CharField(source='get_estado_anterior_display', read_only=True)
    estado_nuevo_display = serializers.CharField(source='get_estado_nuevo_display', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True, default=None)

    class Meta:
        model = HistorialEstado
        fields = [
            'fecha',
            'estado_anterior',
            'estado_anterior_display',
            'estado_nuevo',
            'estado_nuevo_display',
            'usuario_nombre',
            'comentario',
        ]


class PedidoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    tipo_entrega_display = serializers.CharField(source='get_tipo_entrega_display', read_only=True)
    creado_por_nombre = serializers.CharField(source='creado_por.username', read_only=True, default=None)
    detalles = DetallePedidoSerializer(many=True)
    historial = HistorialEstadoSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = [
            'id',
            'cliente',
            'cliente_nombre',
            'estado',
            'estado_display',
            'tipo_entrega',
            'tipo_entrega_display',
            'fecha_entrega',
            'direccion_entrega',
            'diseno',
            'imagen_referencia',
            'observaciones',
            'total',
            'detalles',
            'historial',
            'creado_por_nombre',
            'creado_en',
        ]
        read_only_fields = ['estado', 'imagen_referencia', 'total', 'creado_en']

    def validate(self, attrs):
        if self.instance and self.instance.estado != Pedido.Estado.COTIZACION:
            raise serializers.ValidationError(
                'Solo se pueden modificar pedidos en estado Cotización.'
            )
        if self.instance is None and not attrs.get('detalles'):
            raise serializers.ValidationError({'detalles': 'Agrega al menos un producto.'})

        # Reutilizamos las validaciones del modelo (24 horas, dirección de despacho).
        pedido = copy.copy(self.instance) if self.instance else Pedido()
        for campo, valor in attrs.items():
            if campo != 'detalles':
                setattr(pedido, campo, valor)
        try:
            pedido.clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict)
        return attrs

    def _guardar_detalles(self, pedido, detalles):
        for datos_detalle in detalles:
            personalizaciones = datos_detalle.pop('personalizaciones', [])
            detalle = DetallePedido.objects.create(pedido=pedido, **datos_detalle)
            for datos_perso in personalizaciones:
                PersonalizacionDetalle.objects.create(detalle=detalle, **datos_perso)

    @transaction.atomic
    def create(self, validated_data):
        detalles = validated_data.pop('detalles')
        pedido = Pedido.objects.create(**validated_data)
        self._guardar_detalles(pedido, detalles)
        pedido.calcular_total()
        registrar_cambio(pedido, '', pedido.creado_por, 'Cotización creada')
        return pedido

    @transaction.atomic
    def update(self, instance, validated_data):
        detalles = validated_data.pop('detalles', None)
        pedido = super().update(instance, validated_data)
        if detalles is not None:
            # Al editar una cotización, los productos se reemplazan por la nueva lista.
            pedido.detalles.all().delete()
            self._guardar_detalles(pedido, detalles)
        pedido.calcular_total()
        return pedido


class PedidoKanbanSerializer(serializers.ModelSerializer):
    """Versión resumida del pedido para las tarjetas del tablero Kanban."""

    cliente_nombre = serializers.CharField(source='cliente.nombre', read_only=True)
    productos = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = ['id', 'cliente_nombre', 'fecha_entrega', 'tipo_entrega', 'estado', 'productos', 'diseno']

    def get_productos(self, pedido) -> list[str]:
        return [f'{d.cantidad} x {d.producto.nombre}' for d in pedido.detalles.all()]


class MotivoSerializer(serializers.Serializer):
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=200)


class ImagenReferenciaSerializer(serializers.Serializer):
    imagen_referencia = serializers.ImageField()
