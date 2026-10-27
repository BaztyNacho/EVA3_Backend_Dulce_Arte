"""
Configuración del Django Admin para la app PEDIDOS.
"""

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from inventario.admin import etiqueta, formato_clp

from .models import Cliente, DetallePedido, HistorialEstado, Pedido, PersonalizacionDetalle

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
    readonly_fields = ['total_formateado', 'vista_referencia', 'creado_por', 'creado_en', 'actualizado_en']
    inlines = [DetallePedidoInline, HistorialEstadoInline]
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
        if not change:
            obj.creado_por = request.user
        # Guardamos el estado anterior para registrar la trazabilidad.
        estado_anterior = ''
        if change:
            estado_anterior = Pedido.objects.get(pk=obj.pk).estado
        super().save_model(request, obj, form, change)
        if estado_anterior != obj.estado:
            HistorialEstado.objects.create(
                pedido=obj,
                estado_anterior=estado_anterior,
                estado_nuevo=obj.estado,
                usuario=request.user,
                comentario='Cambio realizado desde el panel de administración',
            )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Regla de negocio: el total se recalcula después de guardar los productos.
        form.instance.calcular_total()


class PersonalizacionDetalleInline(admin.TabularInline):
    model = PersonalizacionDetalle
    extra = 1
    autocomplete_fields = ['opcion']
    fields = ['opcion', 'porciones', 'precio_adicional_formateado']
    readonly_fields = ['precio_adicional_formateado']

    @admin.display(description='Precio adicional')
    def precio_adicional_formateado(self, obj):
        return formato_clp(obj.precio_adicional) if obj.pk else '—'


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