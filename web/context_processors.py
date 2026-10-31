"""
Datos disponibles en todos los templates: el rol del usuario conectado.
"""

from pedidos.permisos import NOMBRES_ROL, rol_principal, roles_de


def roles(request):
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {'es_admin': False, 'es_ventas': False, 'es_cocina': False,
                'es_bodega': False, 'es_repartidor': False, 'rol': None, 'nombre_rol': ''}
    del_usuario = roles_de(usuario)
    rol = rol_principal(usuario)
    return {
        'es_admin': 'admin' in del_usuario,
        'es_ventas': 'ventas' in del_usuario,
        'es_cocina': 'cocina' in del_usuario,
        'es_bodega': 'bodega' in del_usuario,
        'es_repartidor': 'repartidor' in del_usuario,
        'rol': rol,                              # el rol que define la interfaz
        'nombre_rol': NOMBRES_ROL.get(rol, ''),
    }
