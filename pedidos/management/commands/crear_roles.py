"""
Comando para crear los roles (grupos) de Dulce Arte con sus permisos.

Uso:
    python manage.py crear_roles

Se puede ejecutar varias veces sin problema: si los grupos ya existen,
solo actualiza sus permisos.
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ADMINISTRADOR = 'Administrador'
ATENCION_VENTAS = 'Atención y Ventas'

# Permisos del rol Atención y Ventas: (app, modelo, acciones)
PERMISOS_VENTAS = [
    ('pedidos', 'cliente', ['view', 'add', 'change']),
    ('pedidos', 'pedido', ['view', 'add', 'change']),
    ('pedidos', 'detallepedido', ['view', 'add', 'change', 'delete']),
    ('pedidos', 'personalizaciondetalle', ['view', 'add', 'change', 'delete']),
    ('pedidos', 'historialestado', ['view']),
    ('inventario', 'producto', ['view']),
    ('inventario', 'opcionpersonalizacion', ['view']),
]


class Command(BaseCommand):
    help = 'Crea o actualiza los grupos "Administrador" y "Atención y Ventas" con sus permisos.'

    def handle(self, *args, **options):
        # Administrador: todos los permisos de las tres apps del negocio.
        admin_grupo, creado = Group.objects.get_or_create(name=ADMINISTRADOR)
        permisos_admin = Permission.objects.filter(
            content_type__app_label__in=['inventario', 'pedidos', 'despachos']
        )
        admin_grupo.permissions.set(permisos_admin)
        self.stdout.write(
            self.style.SUCCESS(
                f'{"Creado" if creado else "Actualizado"} grupo "{ADMINISTRADOR}" '
                f'con {permisos_admin.count()} permisos.'
            )
        )

        # Atención y Ventas: solo lo necesario para cotizar y registrar pedidos.
        ventas_grupo, creado = Group.objects.get_or_create(name=ATENCION_VENTAS)
        codenames = []
        for app, modelo, acciones in PERMISOS_VENTAS:
            for accion in acciones:
                codenames.append((app, f'{accion}_{modelo}'))
        permisos_ventas = [
            Permission.objects.get(content_type__app_label=app, codename=codename)
            for app, codename in codenames
        ]
        ventas_grupo.permissions.set(permisos_ventas)
        self.stdout.write(
            self.style.SUCCESS(
                f'{"Creado" if creado else "Actualizado"} grupo "{ATENCION_VENTAS}" '
                f'con {len(permisos_ventas)} permisos.'
            )
        )