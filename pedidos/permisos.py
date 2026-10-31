"""
Roles y permisos de Dulce Arte para la API y las vistas web.

- Administrador: superusuario o miembro del grupo "Administrador". Supervisa: en la web y la API
  solo consulta el trabajo de los demás roles; la gestión completa la hace en el Django Admin.
- Atención y Ventas: catálogo, cotizaciones y pedidos.
- Cocina: tablero Kanban y detalle de pedidos.
- Bodega: inventario, entradas y mermas.
- Repartidor: rutas de despacho y entregas con firma.

Los permisos detallados de cada grupo se definen en el comando `crear_roles`.
"""

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS, BasePermission, DjangoModelPermissions
from rest_framework.response import Response

from pedidos.management.commands.crear_roles import (
    ADMINISTRADOR,
    ATENCION_VENTAS,
    BODEGA,
    COCINA,
    REPARTIDOR,
)

# Nombre corto de cada rol -> nombre del grupo en Django
GRUPOS = {
    'ventas': ATENCION_VENTAS,
    'cocina': COCINA,
    'bodega': BODEGA,
    'repartidor': REPARTIDOR,
}
NOMBRES_ROL = {
    'admin': 'Administrador',
    'ventas': 'Atención y Ventas',
    'cocina': 'Cocina',
    'bodega': 'Bodega',
    'repartidor': 'Repartidor',
}


def es_administrador(usuario):
    return usuario.is_authenticated and (
        usuario.is_superuser or usuario.groups.filter(name=ADMINISTRADOR).exists()
    )


def roles_de(usuario):
    """Conjunto de roles del usuario, por ejemplo {'cocina'} o {'admin'}."""
    if not usuario.is_authenticated:
        return set()
    roles = set()
    if es_administrador(usuario):
        roles.add('admin')
    nombres = set(usuario.groups.values_list('name', flat=True))
    roles.update(rol for rol, grupo in GRUPOS.items() if grupo in nombres)
    return roles


def rol_principal(usuario):
    """El rol que define la interfaz del usuario (si tuviera varios, gana el de más alcance)."""
    roles = roles_de(usuario)
    for rol in ['admin', 'ventas', 'cocina', 'bodega', 'repartidor']:
        if rol in roles:
            return rol
    return None


def es_ventas(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name=ATENCION_VENTAS).exists()


def es_cocina(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name=COCINA).exists()


def es_bodega(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name=BODEGA).exists()


def es_repartidor(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name=REPARTIDOR).exists()


class PermisosDelModelo(DjangoModelPermissions):
    """
    Usa los permisos de Django asignados a cada grupo:
    GET -> ver, POST -> agregar, PUT/PATCH -> modificar, DELETE -> eliminar.
    (Por defecto DRF no exige el permiso "ver" en GET; aquí sí.)
    """

    perms_map = {
        **DjangoModelPermissions.perms_map,
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'HEAD': ['%(app_label)s.view_%(model_name)s'],
    }


class EsAdministrador(BasePermission):
    message = 'Solo el Administrador puede realizar esta acción.'

    def has_permission(self, request, view):
        return es_administrador(request.user)


def _rol_o_admin_mirando(request, es_del_rol):
    """El rol puede operar; el Administrador solo puede consultar (GET)."""
    if es_del_rol(request.user):
        return True
    return es_administrador(request.user) and request.method in SAFE_METHODS


class EsAdminOCocina(BasePermission):
    message = 'Solo Cocina puede mover pedidos entre etapas. El Administrador solo puede consultar.'

    def has_permission(self, request, view):
        return _rol_o_admin_mirando(request, es_cocina)


class EsAdminOBodega(BasePermission):
    message = 'Solo Bodega puede registrar movimientos. El Administrador solo puede consultar.'

    def has_permission(self, request, view):
        return _rol_o_admin_mirando(request, es_bodega)


class EsAdminORepartidor(BasePermission):
    message = 'Solo el Repartidor puede gestionar rutas y entregas. El Administrador solo puede consultar.'

    def has_permission(self, request, view):
        return _rol_o_admin_mirando(request, es_repartidor)


class AdminSoloLectura(BasePermission):
    """
    El Administrador no interfiere en el trabajo de Ventas: en la API solo consulta
    pedidos y clientes (los gestiona desde el Django Admin si es necesario).
    """

    message = 'El Administrador solo puede consultar pedidos y clientes desde la web y la API.'

    def has_permission(self, request, view):
        if es_administrador(request.user) and not es_ventas(request.user):
            return request.method in SAFE_METHODS
        return True


class AdminOBodegaSoloLectura(BasePermission):
    """El Administrador puede gestionar insumos; Bodega solo consultarlos (GET)."""

    message = 'Solo el Administrador puede crear o modificar insumos.'

    def has_permission(self, request, view):
        if es_administrador(request.user):
            return True
        return request.method in SAFE_METHODS and es_bodega(request.user)


class ProtegidoContraBorradoMixin:
    """
    Si se intenta borrar un registro que otros usan (por ejemplo, un insumo que está
    en una receta), responde con un mensaje claro en vez de un error del servidor.
    """

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'No se puede eliminar: este registro está siendo usado por otros datos. '
                           'Puedes marcarlo como inactivo.'},
                status=status.HTTP_409_CONFLICT,
            )
