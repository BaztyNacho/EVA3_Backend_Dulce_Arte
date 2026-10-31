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
COCINA = 'Cocina'
BODEGA = 'Bodega'
REPARTIDOR = 'Repartidor'

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

# Cocina: ve los pedidos completos (con precios) para preparar; las etapas se mueven con la API del Kanban.
PERMISOS_COCINA = [
    ('pedidos', 'cliente', ['view']),
    ('pedidos', 'pedido', ['view']),
    ('pedidos', 'detallepedido', ['view']),
    ('pedidos', 'personalizaciondetalle', ['view']),
    ('pedidos', 'historialestado', ['view']),
    ('inventario', 'producto', ['view']),
    ('inventario', 'recetaitem', ['view']),
    ('inventario', 'opcionpersonalizacion', ['view']),
    ('inventario', 'insumo', ['view']),
]

# Bodega: ve el inventario y registra entradas y mermas (no crea ni edita insumos ni recetas).
PERMISOS_BODEGA = [
    ('inventario', 'insumo', ['view']),
    ('inventario', 'movimientoinsumo', ['view', 'add']),
    ('inventario', 'producto', ['view']),
    ('inventario', 'recetaitem', ['view']),
]

# Repartidor: gestiona las rutas y confirma las entregas.
PERMISOS_REPARTIDOR = [
    ('despachos', 'ruta', ['view', 'add', 'change']),
    ('despachos', 'despacho', ['view', 'change']),
    ('pedidos', 'pedido', ['view']),
    ('pedidos', 'cliente', ['view']),
]


class Command(BaseCommand):
    help = 'Crea o actualiza los grupos de Dulce Arte (Administrador, Atención y Ventas, Cocina, Bodega y Repartidor).'

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

        # Roles con permisos acotados a su puesto de trabajo
        for nombre, lista in [
            (ATENCION_VENTAS, PERMISOS_VENTAS),
            (COCINA, PERMISOS_COCINA),
            (BODEGA, PERMISOS_BODEGA),
            (REPARTIDOR, PERMISOS_REPARTIDOR),
        ]:
            grupo, creado = Group.objects.get_or_create(name=nombre)
            permisos = [
                Permission.objects.get(content_type__app_label=app, codename=f'{accion}_{modelo}')
                for app, modelo, acciones in lista
                for accion in acciones
            ]
            grupo.permissions.set(permisos)
            self.stdout.write(
                self.style.SUCCESS(
                    f'{"Creado" if creado else "Actualizado"} grupo "{nombre}" con {len(permisos)} permisos.'
                )
            )
