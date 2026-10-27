"""
Configuración del Django Admin para la app DESPACHOS.
"""

from django.contrib import admin
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from inventario.admin import etiqueta

from .models import Despacho, Ruta
from .services import marcar_pedido_entregado

COLORES_DESPACHO = {
    Despacho.Estado.PENDIENTE: ('#F1EFE8', '#444441'),
    Despacho.Estado.EN_CAMINO: ('#FFF1D6', '#8A5A00'),
    Despacho.Estado.ENTREGADO: ('#E3F4E8', '#1E6B3A'),
    Despacho.Estado.FALLIDO: ('#FDE2E4', '#9B1C31'),
}

COLORES_RUTA = {
    Ruta.Estado.PLANIFICADA: ('#E3EEFB', '#1B4F8A'),
    Ruta.Estado.EN_CURSO: ('#FFF1D6', '#8A5A00'),
    Ruta.Estado.FINALIZADA: ('#E3F4E8', '#1E6B3A'),
}


class DespachoInline(admin.TabularInline):
    model = Despacho
    extra = 1
    fields = ['orden', 'pedido', 'estado']
    autocomplete_fields = ['pedido']
    show_change_link = True
    ordering = ['orden']


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'fecha', 'responsable', 'estado_coloreado', 'cantidad_despachos']
    list_filter = ['estado', 'fecha', 'responsable']
    search_fields = ['nombre']
    date_hierarchy = 'fecha'
    inlines = [DespachoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_despachos=Count('despachos'))

    @admin.display(description='Estado', ordering='estado')
    def estado_coloreado(self, obj):
        fondo, texto = COLORES_RUTA.get(obj.estado, ('#EEE', '#333'))
        return etiqueta(obj.get_estado_display(), fondo, texto)

    @admin.display(description='Despachos', ordering='num_despachos')
    def cantidad_despachos(self, obj):
        return obj.num_despachos


@admin.register(Despacho)
class DespachoAdmin(admin.ModelAdmin):
    list_display = [
        'pedido',
        'cliente',
        'direccion',
        'ruta',
        'orden',
        'estado_coloreado',
        'tiene_evidencia',
        'fecha_entrega_real',
    ]
    list_filter = ['estado', 'ruta']
    search_fields = ['pedido__id', 'pedido__cliente__nombre', 'pedido__direccion_entrega', 'nombre_receptor']
    autocomplete_fields = ['pedido', 'ruta']
    readonly_fields = ['vista_firma', 'vista_comprobante']
    fieldsets = [
        ('Pedido y ruta', {'fields': ['pedido', 'ruta', 'orden', 'estado']}),
        ('Confirmación de entrega', {
            'fields': [
                'nombre_receptor',
                'fecha_entrega_real',
                'firma',
                'vista_firma',
                'comprobante',
                'vista_comprobante',
                'observaciones',
            ]
        }),
    ]

    @admin.display(description='Cliente', ordering='pedido__cliente__nombre')
    def cliente(self, obj):
        return obj.pedido.cliente.nombre

    @admin.display(description='Dirección')
    def direccion(self, obj):
        return obj.pedido.direccion_entrega

    @admin.display(description='Estado', ordering='estado')
    def estado_coloreado(self, obj):
        fondo, texto = COLORES_DESPACHO.get(obj.estado, ('#EEE', '#333'))
        return etiqueta(obj.get_estado_display(), fondo, texto)

    @admin.display(description='Evidencia', boolean=True)
    def tiene_evidencia(self, obj):
        return bool(obj.firma or obj.comprobante)

    @admin.display(description='Vista de la firma')
    def vista_firma(self, obj):
        if obj.firma:
            return format_html(
                '<img src="{}" style="max-width:280px;background:#fff;border:1px solid #ddd;border-radius:8px;">',
                obj.firma.url,
            )
        return 'Sin firma'

    @admin.display(description='Vista del comprobante')
    def vista_comprobante(self, obj):
        if obj.comprobante:
            return format_html(
                '<img src="{}" style="max-width:280px;border-radius:8px;">', obj.comprobante.url
            )
        return 'Sin comprobante'

    def save_model(self, request, obj, form, change):
        if obj.estado == Despacho.Estado.ENTREGADO and not obj.fecha_entrega_real:
            obj.fecha_entrega_real = timezone.now()
        super().save_model(request, obj, form, change)
        # Al entregar el despacho, el pedido también pasa a "Entregado" (con trazabilidad).
        if obj.estado == Despacho.Estado.ENTREGADO:
            marcar_pedido_entregado(obj, request.user)
