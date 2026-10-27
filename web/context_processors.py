"""
Datos disponibles en todos los templates: el rol del usuario conectado.
"""

from pedidos.permisos import es_administrador, es_ventas


def roles(request):
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {'es_admin': False, 'es_ventas': False}
    return {'es_admin': es_administrador(usuario), 'es_ventas': es_ventas(usuario)}
