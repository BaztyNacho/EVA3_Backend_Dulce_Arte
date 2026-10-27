"""
Roles y permisos de Dulce Arte para la API y las vistas web.

- Administrador: superusuario o miembro del grupo "Administrador".
- Atención y Ventas: miembro del grupo "Atención y Ventas".

Los permisos detallados de cada grupo se definen en el comando `crear_roles`.
"""

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.permissions import BasePermission, DjangoModelPermissions
from rest_framework.response import Response

from pedidos.management.commands.crear_roles import ADMINISTRADOR, ATENCION_VENTAS


def es_administrador(usuario):
    return usuario.is_authenticated and (
        usuario.is_superuser or usuario.groups.filter(name=ADMINISTRADOR).exists()
    )


def es_ventas(usuario):
    return usuario.is_authenticated and usuario.groups.filter(name=ATENCION_VENTAS).exists()


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
