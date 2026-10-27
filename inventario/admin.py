"""
Configuración del Django Admin para la app INVENTARIO.
"""

from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, F
from django.utils.html import format_html

from .models import Insumo, MovimientoInsumo, OpcionPersonalizacion, Producto, RecetaItem


def formato_clp(valor):
    """Muestra un número como pesos chilenos: 25000 -> $25.000"""
    return f'${valor:,.0f}'.replace(',', '.')


def etiqueta(texto, color_fondo, color_texto):
    """Genera una 'píldora' de color para destacar estados en los listados."""
    return format_html(
        '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;'
        'font-weight:600;font-size:11px;white-space:nowrap;">{}</span>',
        color_fondo,
        color_texto,
        texto,
    )


# ---------------------------------------------------------------
# Filtro personalizado: insumos con stock bajo
# ---------------------------------------------------------------
class StockBajoFilter(admin.SimpleListFilter):
    title = 'estado del stock'
    parameter_name = 'stock'

    def lookups(self, request, model_admin):
        return [('bajo', 'Stock bajo'), ('ok', 'Stock suficiente')]

    def queryset(self, request, queryset):
        if self.value() == 'bajo':
            return queryset.filter(stock_actual__lte=F('stock_minimo'))
        if self.value() == 'ok':
            return queryset.filter(stock_actual__gt=F('stock_minimo'))
        return queryset


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = [
        'nombre',
        'unidad',
        'stock_actual',
        'stock_minimo',
        'estado_stock',
        'costo_formateado',
        'activo',
    ]
    list_filter = [StockBajoFilter, 'unidad', 'activo']
    search_fields = ['nombre']
    list_editable = ['activo']
    readonly_fields = ['creado_en', 'actualizado_en']
    fieldsets = [
        ('Datos del insumo', {'fields': ['nombre', 'unidad', 'costo_unitario', 'activo']}),
        ('Control de stock', {'fields': ['stock_actual', 'stock_minimo']}),
        ('Auditoría', {'fields': ['creado_en', 'actualizado_en'], 'classes': ['collapse']}),
    ]

    def get_readonly_fields(self, request, obj=None):
        # El stock inicial se ingresa al crear el insumo. Después, solo cambia
        # mediante Movimientos de insumos, para que quede trazabilidad.
        if obj:
            return self.readonly_fields + ['stock_actual']
        return self.readonly_fields

    @admin.display(description='Estado')
    def estado_stock(self, obj):
        if obj.stock_bajo:
            return etiqueta('Stock bajo', '#FDE2E4', '#9B1C31')
        return etiqueta('Suficiente', '#E3F4E8', '#1E6B3A')

    @admin.display(description='Costo unitario', ordering='costo_unitario')
    def costo_formateado(self, obj):
        return formato_clp(obj.costo_unitario)


class RecetaItemInline(admin.TabularInline):
    """Permite editar la receta (BOM) directamente dentro del producto."""

    model = RecetaItem
    extra = 1
    autocomplete_fields = ['insumo']
    verbose_name = 'insumo de la receta'
    verbose_name_plural = 'Receta del producto (lista de materiales por unidad)'


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = [
        'miniatura',
        'nombre',
        'categoria',
        'precio_formateado',
        'insumos_en_receta',
        'activo',
    ]
    list_display_links = ['miniatura', 'nombre']
    list_filter = ['categoria', 'activo']
    search_fields = ['nombre', 'descripcion']
    list_editable = ['activo']
    readonly_fields = ['vista_previa', 'creado_en', 'actualizado_en']
    inlines = [RecetaItemInline]
    fieldsets = [
        ('Datos del producto', {'fields': ['nombre', 'categoria', 'descripcion', 'precio_base', 'activo']}),
        ('Imagen', {'fields': ['imagen', 'vista_previa']}),
        ('Auditoría', {'fields': ['creado_en', 'actualizado_en'], 'classes': ['collapse']}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(num_insumos=Count('receta'))

    @admin.display(description='Foto')
    def miniatura(self, obj):
        if obj.imagen:
            return format_html(
                '<img src="{}" style="width:48px;height:48px;object-fit:cover;border-radius:8px;">',
                obj.imagen.url,
            )
        return '—'

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        if obj.imagen:
            return format_html(
                '<img src="{}" style="max-width:240px;border-radius:12px;">', obj.imagen.url
            )
        return 'Sin imagen'

    @admin.display(description='Precio base', ordering='precio_base')
    def precio_formateado(self, obj):
        return formato_clp(obj.precio_base)

    @admin.display(description='Insumos en receta', ordering='num_insumos')
    def insumos_en_receta(self, obj):
        if obj.num_insumos == 0:
            return etiqueta('Sin receta', '#FFF1D6', '#8A5A00')
        return obj.num_insumos


@admin.register(OpcionPersonalizacion)
class OpcionPersonalizacionAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'insumo', 'cantidad_por_porcion', 'precio_formateado', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre', 'insumo__nombre']
    list_editable = ['activo']
    autocomplete_fields = ['insumo']

    @admin.display(description='Precio por porción', ordering='precio_por_porcion')
    def precio_formateado(self, obj):
        return formato_clp(obj.precio_por_porcion)


class MovimientoInsumoForm(forms.ModelForm):
    """Formulario que valida que el stock nunca quede negativo."""

    class Meta:
        model = MovimientoInsumo
        fields = ['insumo', 'tipo', 'cantidad', 'motivo']

    def clean(self):
        datos = super().clean()
        insumo = datos.get('insumo')
        tipo = datos.get('tipo')
        cantidad = datos.get('cantidad')
        resta = tipo in (MovimientoInsumo.Tipo.SALIDA, MovimientoInsumo.Tipo.AJUSTE)
        if insumo and cantidad and resta and cantidad > insumo.stock_actual:
            raise forms.ValidationError(
                f'No hay stock suficiente de {insumo.nombre}: '
                f'hay {insumo.stock_actual} {insumo.unidad} y se intenta descontar {cantidad}.'
            )
        return datos


@admin.register(MovimientoInsumo)
class MovimientoInsumoAdmin(admin.ModelAdmin):
    """
    Los movimientos son el registro de trazabilidad de bodega:
    al crearlos se actualiza el stock, y luego NO se pueden editar ni borrar.
    Entrada y Devolución suman stock. Salida y Ajuste (merma) restan stock.
    """

    form = MovimientoInsumoForm
    list_display = ['fecha', 'insumo', 'tipo_coloreado', 'cantidad', 'motivo', 'pedido', 'usuario']
    list_filter = ['tipo', 'insumo', 'fecha']
    search_fields = ['insumo__nombre', 'motivo']
    date_hierarchy = 'fecha'
    autocomplete_fields = ['insumo']

    COLORES = {
        MovimientoInsumo.Tipo.ENTRADA: ('#E3F4E8', '#1E6B3A'),
        MovimientoInsumo.Tipo.DEVOLUCION: ('#E3EEFB', '#1B4F8A'),
        MovimientoInsumo.Tipo.SALIDA: ('#FDE2E4', '#9B1C31'),
        MovimientoInsumo.Tipo.AJUSTE: ('#FFF1D6', '#8A5A00'),
    }

    @admin.display(description='Tipo', ordering='tipo')
    def tipo_coloreado(self, obj):
        fondo, texto = self.COLORES.get(obj.tipo, ('#EEE', '#333'))
        return etiqueta(obj.get_tipo_display(), fondo, texto)

    def get_fields(self, request, obj=None):
        if obj:
            return ['insumo', 'tipo', 'cantidad', 'motivo', 'pedido', 'usuario', 'fecha']
        return ['insumo', 'tipo', 'cantidad', 'motivo']

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Un movimiento ya registrado no se modifica.
            return ['insumo', 'tipo', 'cantidad', 'motivo', 'pedido', 'usuario', 'fecha']
        return []

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            return
        suma = obj.tipo in (MovimientoInsumo.Tipo.ENTRADA, MovimientoInsumo.Tipo.DEVOLUCION)
        with transaction.atomic():
            insumo = Insumo.objects.select_for_update().get(pk=obj.insumo_id)
            if suma:
                insumo.stock_actual += obj.cantidad
            else:
                insumo.stock_actual -= obj.cantidad
            insumo.save(update_fields=['stock_actual', 'actualizado_en'])
            obj.usuario = request.user
            super().save_model(request, obj, form, change)
        if insumo.stock_bajo:
            messages.warning(request, f'Atención: {insumo.nombre} quedó con stock bajo.')