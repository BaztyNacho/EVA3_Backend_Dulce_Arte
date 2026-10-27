"""
Serializers de INVENTARIO: convierten los modelos a JSON (y validan el JSON que llega).
"""

from rest_framework import serializers

from .models import Insumo, MovimientoInsumo, OpcionPersonalizacion, Producto, RecetaItem


class InsumoSerializer(serializers.ModelSerializer):
    unidad_display = serializers.CharField(source='get_unidad_display', read_only=True)
    stock_bajo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Insumo
        fields = [
            'id',
            'nombre',
            'unidad',
            'unidad_display',
            'stock_actual',
            'stock_minimo',
            'stock_bajo',
            'costo_unitario',
            'activo',
        ]

    def update(self, instance, validated_data):
        # El stock solo cambia mediante movimientos (trazabilidad).
        validated_data.pop('stock_actual', None)
        return super().update(instance, validated_data)


class RecetaItemSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    unidad = serializers.CharField(source='insumo.unidad', read_only=True)

    class Meta:
        model = RecetaItem
        fields = ['insumo', 'insumo_nombre', 'unidad', 'cantidad']


class ProductoSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)
    receta = RecetaItemSerializer(many=True, read_only=True)

    class Meta:
        model = Producto
        fields = [
            'id',
            'nombre',
            'categoria',
            'categoria_display',
            'descripcion',
            'precio_base',
            'imagen',
            'activo',
            'receta',
        ]


class OpcionPersonalizacionSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)

    class Meta:
        model = OpcionPersonalizacion
        fields = [
            'id',
            'nombre',
            'insumo',
            'insumo_nombre',
            'cantidad_por_porcion',
            'precio_por_porcion',
            'activo',
        ]


class MovimientoInsumoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True, default=None)

    class Meta:
        model = MovimientoInsumo
        fields = [
            'id',
            'insumo',
            'insumo_nombre',
            'tipo',
            'tipo_display',
            'cantidad',
            'motivo',
            'pedido',
            'usuario_nombre',
            'fecha',
        ]
        read_only_fields = ['pedido', 'fecha']
