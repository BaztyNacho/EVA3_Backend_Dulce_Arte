"""
Filtros de template propios de Dulce Arte.
Uso en un template: {% load dulce %} y luego {{ pedido.total|clp }}
"""

from django import template

register = template.Library()


@register.filter
def clp(valor):
    """25000 -> $25.000"""
    try:
        return f'${int(valor):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return valor


@register.filter
def porcentaje(parte, total):
    """Porcentaje entre 0 y 100, para las barras de stock."""
    try:
        if not total:
            return 100
        return max(0, min(100, round(float(parte) / float(total) * 100)))
    except (TypeError, ValueError):
        return 0
