"""
Configuración del Django Admin para la app PEDIDOS.
"""

from django.contrib import admin, messages
from django.db.models import Count
from django.utils.html import format_html

from inventario.admin import etiqueta, formato_clp

from .models import Cliente, DetallePedido, HistorialEstado, Pedido, PersonalizacionDetalle
from .services import (
    ReglaNegocioError,
    avanzar_estado,
    cancelar_pedido,
    confirmar_cotizacion,
    rechazar_control_calidad,
)

# Colores de cada estado del pedido (fondo, texto)
COLORES_ESTADO = {
    Pedido.Estado.COTIZACION: ('#F1EFE8', '#444441'),
    Pedido.Estado.RECIBIDO: ('#E3EEFB', '#1B4F8A'),
    Pedido.Estado.EN_PREPARACION: ('#FFF1D6', '#8A5A00'),
    Pedido.Estado.HORNEADO_DECORADO: ('#FBE4D8', '#8A3B12'),
    Pedido.Estado.CONTROL_CALIDAD: ('#EEE6FA', '#5B3A99'),
    Pedido.Estado.LISTO: ('#E3F4E8', '#1E6B3A'),
    Pedido.Estado.EN_DESPACHO: ('#FCE4EC', '#9C2A55'),
    Pedido.Estado.ENTREGADO: ('#D6F0DE', '#14532D'),
    Pedido.Estado.CANCELADO: ('#FDE2E4', '#9B1C31'),
}


def etiqueta_estado(pedido):
    fondo, texto = COLORES_ESTADO.get(pedido.estado, ('#EEE', '#333'))
    return etiqueta(pedido.get_estado_display(), fondo, texto)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'telefono', 'email', 'total_pedidos', 'creado_en']
    search_fields = ['nombre', 'telefono', 'email']
    list_filter = ['creado_en']
    readonly_fields = ['creado_en']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_pedidos=Count('pedidos'))

    @admin.display(description='Pedidos', ordering='num_pedidos')
    def total_pedidos(self, obj):
        return obj.num_pedidos


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 1
    autocomplete_fields = ['producto']
    fields = ['producto', 'cantidad', 'precio_unitario', 'comentario', 'subtotal_formateado']
    readonly_fields = ['precio_unitario', 'subtotal_formateado']
    show_change_link = True  # enlace para agregar personalizaciones al producto

    @admin.display(description='Subtotal')
    def subtotal_formateado(self, obj):
        return formato_clp(obj.subtotal) if obj.pk else '—'

    # Regla de negocio: los productos solo se modifican mientras el pedido es cotización,
    # porque al confirmarlo ya se descontaron los insumos.
    def _es_editable(self, pedido):
        return pedido is None or pedido.estado == Pedido.Estado.COTIZACION

    def has_add_permission(self, request, obj=None):
        return self._es_editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._es_editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._es_editable(obj) and super().has_delete_permission(request, obj)


class HistorialEstadoInline(admin.TabularInline):
    """Trazabilidad del pedido: solo lectura."""

    model = HistorialEstado
    extra = 0
    fields = ['fecha', 'estado_anterior', 'estado_nuevo', 'usuario', 'comentario']
    readonly_fields = fields
    can_delete = False
    verbose_name_plural = 'Historial de estados (trazabilidad)'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = [
        'numero',
        'cliente',
        'fecha_entrega',
        'estado_coloreado',
        'tipo_entrega',
        'total_formateado',
        'creado_por',
    ]
    list_display_links = ['numero', 'cliente']
    list_filter = ['estado', 'tipo_entrega', 'fecha_entrega', 'creado_en']
    search_fields = ['id', 'cliente__nombre', 'cliente__telefono', 'diseno']
    date_hierarchy = 'fecha_entrega'
    autocomplete_fields = ['cliente']
    readonly_fields = [
        'estado',
        'total_formateado',
        'vista_referencia',
        'creado_por',
        'creado_en',
        'actualizado_en',
    ]
    inlines = [DetallePedidoInline, HistorialEstadoInline]
    actions = ['accion_confirmar', 'accion_avanzar', 'accion_rechazar_calidad', 'accion_cancelar']
    fieldsets = [
        ('Cliente y entrega', {'fields': ['cliente', 'fecha_entrega', 'tipo_entrega', 'direccion_entrega']}),
        ('Estado', {'fields': ['estado', 'total_formateado']}),
        ('Diseño personalizado', {'fields': ['diseno', 'imagen_referencia', 'vista_referencia', 'observaciones']}),
        ('Auditoría', {'fields': ['creado_por', 'creado_en', 'actualizado_en'], 'classes': ['collapse']}),
    ]

    @admin.display(description='N°', ordering='id')
    def numero(self, obj):
        return f'#{obj.pk}'

    @admin.display(description='Estado', ordering='estado')
    def estado_coloreado(self, obj):
        return etiqueta_estado(obj)

    @admin.display(description='Total', ordering='total')
    def total_formateado(self, obj):
        return formato_clp(obj.total)

    @admin.display(description='Vista previa')
    def vista_referencia(self, obj):
        if obj.imagen_referencia:
            return format_html(
                '<img src="{}" style="max-width:240px;border-radius:12px;">',
                obj.imagen_referencia.url,
            )
        return 'Sin imagen de referencia'

    def save_model(self, request, obj, form, change):
        nuevo = not change
        if nuevo:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
        if nuevo:
            HistorialEstado.objects.create(
                pedido=obj,
                estado_nuevo=obj.estado,
                usuario=request.user,
                comentario='Cotización creada',
            )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Regla de negocio: el total se recalcula después de guardar los productos.
        form.instance.calcular_total()

    # ---------------------------------------------------------------
    # Acciones: los cambios de estado SOLO se hacen con estas acciones,
    # que aplican las reglas de negocio de pedidos/services.py
    # ---------------------------------------------------------------
    def _ejecutar(self, request, queryset, funcion, mensaje_exito):
        for pedido in queryset:
            try:
                resultado = funcion(pedido, request.user)
            except ReglaNegocioError as error:
                self.message_user(request, str(error), messages.ERROR)
                continue
            self.message_user(request, mensaje_exito.format(pedido=pedido), messages.SUCCESS)
            if funcion is confirmar_cotizacion and resultado:
                nombres = ', '.join(insumo.nombre for insumo in resultado)
                self.message_user(
                    request, f'Atención: quedaron con stock bajo: {nombres}.', messages.WARNING
                )

    @admin.action(description='Confirmar cotización (descuenta insumos)')
    def accion_confirmar(self, request, queryset):
        self._ejecutar(
            request, queryset, confirmar_cotizacion,
            'Pedido #{pedido.pk} confirmado: insumos descontados y enviado a cocina.',
        )

    @admin.action(description='Avanzar al siguiente estado del Kanban')
    def accion_avanzar(self, request, queryset):
        self._ejecutar(request, queryset, avanzar_estado, 'Pedido #{pedido.pk} avanzó de estado.')

    @admin.action(description='Rechazar en control de calidad (vuelve a preparación)')
    def accion_rechazar_calidad(self, request, queryset):
        self._ejecutar(
            request, queryset, rechazar_control_calidad,
            'Pedido #{pedido.pk} devuelto a En Preparación.',
        )

    @admin.action(description='Cancelar pedido')
    def accion_cancelar(self, request, queryset):
        self._ejecutar(request, queryset, cancelar_pedido, 'Pedido #{pedido.pk} cancelado.')


class PersonalizacionDetalleInline(admin.TabularInline):
    model = PersonalizacionDetalle
    extra = 1
    autocomplete_fields = ['opcion']
    fields = ['opcion', 'porciones', 'precio_adicional_formateado']
    readonly_fields = ['precio_adicional_formateado']

    @admin.display(description='Precio adicional')
    def precio_adicional_formateado(self, obj):
        return formato_clp(obj.precio_adicional) if obj.pk else '—'

    def _es_editable(self, detalle):
        return detalle is None or detalle.pedido.estado == Pedido.Estado.COTIZACION

    def has_add_permission(self, request, obj=None):
        return self._es_editable(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._es_editable(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._es_editable(obj) and super().has_delete_permission(request, obj)


@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    """Detalle de un producto del pedido, con sus personalizaciones."""

    list_display = ['pedido', 'producto', 'cantidad', 'subtotal_formateado']
    list_filter = ['producto']
    search_fields = ['pedido__id', 'pedido__cliente__nombre', 'producto__nombre']
    autocomplete_fields = ['pedido', 'producto']
    readonly_fields = ['precio_unitario', 'subtotal_formateado']
    inlines = [PersonalizacionDetalleInline]

    @admin.display(description='Subtotal')
    def subtotal_formateado(self, obj):
        return formato_clp(obj.subtotal)

    def has_change_permission(self, request, obj=None):
        if obj and obj.pedido.estado != Pedido.Estado.COTIZACION:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.pedido.estado != Pedido.Estado.COTIZACION:
            return False
        return super().has_delete_permission(request, obj)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.pedido.calcular_total()


@admin.register(HistorialEstado)
class HistorialEstadoAdmin(admin.ModelAdmin):
    """Vista general de la trazabilidad. Solo lectura."""

    list_display = ['fecha', 'pedido', 'estado_anterior', 'estado_nuevo', 'usuario']
    list_filter = ['estado_nuevo', 'fecha']
    search_fields = ['pedido__id', 'pedido__cliente__nombre']
    date_hierarchy = 'fecha'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False