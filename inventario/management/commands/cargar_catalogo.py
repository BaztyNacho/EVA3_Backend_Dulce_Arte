"""
Carga el catálogo inicial de Dulce Arte: insumos, productos, recetas (BOM) y extras.

Uso:
    python manage.py cargar_catalogo

Se puede ejecutar varias veces sin duplicar nada:
- Los insumos que ya existen conservan su stock actual (solo se actualiza unidad, costo y mínimo).
- Los productos actualizan precio y descripción, y su receta se reemplaza por la de este archivo.
- Los extras se actualizan y se vinculan a sus productos.
- Las fotos de inventario/fotos/ se asignan solo a productos e insumos que aún no tienen
  imagen (una foto subida desde el Admin nunca se reemplaza).

Precios y costos aproximados en pesos chilenos (CLP), octubre de 2026.
"""

from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from inventario.models import Insumo, OpcionPersonalizacion, Producto, RecetaItem

D = Decimal

# Carpeta con las fotos iniciales (sí se sube a GitHub, a diferencia de media/).
CARPETA_FOTOS = Path(__file__).resolve().parents[2] / 'fotos'
EXTENSIONES = ('.jpg', '.jpeg', '.png', '.webp')

# Fotos de productos: nombre del producto -> nombre del archivo (sin extensión).
FOTOS_PRODUCTOS = {
    'Torta Chocolate Trufada': 'torta-trufada',
    'Torta Tres Leches': 'torta-tres-leches',
    'Torta Mil Hojas Manjar Nuez': 'torta-mil-hojas',
    'Torta Selva Negra': 'torta-selva-negra',
    'Torta de Lúcuma Manjar': 'torta-lucuma',
    'Cheesecake de Frambuesa': 'cheesecake-frambuesa',
    'Cupcakes Red Velvet (6 un)': 'cupcakes-red-velvet',
    'Cupcakes Vainilla y Frutilla (6 un)': 'cupcakes-vainilla-frutilla',
    'Pie de Limón': 'pie-limon',
    'Tiramisú (8 porciones)': 'tiramisu',
    'Brownies con Nuez (caja 12 un)': 'brownies-nuez',
}
# Las fotos de insumos usan el nombre del insumo en minúsculas, sin tildes y con guiones.
# Ejemplo: "Azúcar flor" -> fotos/insumos/azucar-flor.jpg

# ---------------------------------------------------------------
# INSUMOS: nombre -> (unidad, costo por unidad CLP, stock inicial, stock mínimo)
# ---------------------------------------------------------------
INSUMOS = {
    'Harina sin polvos de hornear': ('kg', 1300, D('40'), D('8')),
    'Azúcar granulada': ('kg', 1400, D('30'), D('6')),
    'Azúcar flor': ('kg', 2200, D('8'), D('2')),
    'Mantequilla sin sal': ('kg', 11000, D('12'), D('3')),
    'Huevos': ('un', 260, D('300'), D('60')),
    'Leche entera': ('l', 1200, D('20'), D('5')),
    'Crema para batir': ('l', 6500, D('15'), D('4')),
    'Leche condensada (lata 397 g)': ('un', 1800, D('24'), D('6')),
    'Esencia de vainilla': ('ml', 25, D('500'), D('100')),
    'Polvos de hornear': ('kg', 9000, D('2'), D('0.5')),
    'Chocolate de cobertura semiamargo': ('kg', 13000, D('10'), D('2')),
    'Cacao amargo en polvo': ('kg', 12000, D('3'), D('0.5')),
    'Manjar': ('kg', 4500, D('15'), D('4')),
    'Nueces mariposa': ('kg', 14000, D('4'), D('1')),
    'Almendras laminadas': ('kg', 16000, D('2'), D('0.5')),
    'Pulpa de lúcuma': ('kg', 9000, D('5'), D('1.5')),
    'Cerezas en almíbar': ('kg', 9000, D('4'), D('1')),
    'Frutillas': ('kg', 4000, D('6'), D('2')),
    # Stock bajo a propósito, para mostrar la alerta en la defensa.
    'Frambuesas': ('kg', 8500, D('0.8'), D('1')),
    'Arándanos': ('kg', 7500, D('3'), D('1')),
    'Queso crema': ('kg', 9500, D('6'), D('1.5')),
    'Galletas de vainilla': ('kg', 5000, D('4'), D('1')),
    'Limones': ('un', 250, D('40'), D('10')),
    'Queso mascarpone': ('kg', 18000, D('3'), D('1')),
    'Bizcochos de soletilla': ('kg', 8000, D('3'), D('1')),
    'Café molido': ('kg', 16000, D('1'), D('0.2')),
    'Colorante rojo en gel': ('g', 30, D('200'), D('50')),
    'Granas de colores': ('kg', 12000, D('1'), D('0.2')),
    'Coco rallado': ('kg', 6000, D('2'), D('0.5')),
    'Crema de avellanas': ('kg', 14000, D('2'), D('0.5')),
}

# ---------------------------------------------------------------
# EXTRAS: nombre -> (insumo, cantidad por porción, precio por porción CLP)
# ---------------------------------------------------------------
EXTRAS = {
    'Chocolate extra': ('Chocolate de cobertura semiamargo', D('0.05'), 1500),
    'Frambuesas extra': ('Frambuesas', D('0.08'), 1800),
    'Frutillas frescas': ('Frutillas', D('0.1'), 1500),
    'Manjar extra': ('Manjar', D('0.15'), 1200),
    'Crema chantilly extra': ('Crema para batir', D('0.15'), 1300),
    'Nueces extra': ('Nueces mariposa', D('0.05'), 1500),
    'Almendras laminadas': ('Almendras laminadas', D('0.04'), 1400),
    'Cerezas extra': ('Cerezas en almíbar', D('0.1'), 1500),
    'Lúcuma extra': ('Pulpa de lúcuma', D('0.1'), 1600),
    'Arándanos': ('Arándanos', D('0.08'), 1800),
    'Frosting de queso crema extra': ('Queso crema', D('0.06'), 1200),
    'Granas de colores': ('Granas de colores', D('0.02'), 800),
    'Merengue extra': ('Azúcar granulada', D('0.05'), 1000),
    'Ralladura de limón extra': ('Limones', D('1'), 500),
    'Coco rallado': ('Coco rallado', D('0.03'), 700),
    'Cacao extra': ('Cacao amargo en polvo', D('0.01'), 600),
    'Café extra': ('Café molido', D('0.01'), 800),
    'Crema de avellanas': ('Crema de avellanas', D('0.06'), 1800),
}

# ---------------------------------------------------------------
# PRODUCTOS: receta por UNA unidad del producto, tiempo de preparación (minutos) y extras
# ---------------------------------------------------------------
PRODUCTOS = [
    {
        'nombre': 'Torta Chocolate Trufada',
        'tiempo': 180,
        'categoria': 'torta',
        'precio': 28000,
        'descripcion': 'Bizcocho húmedo de chocolate relleno con ganache trufada. Rinde 15 porciones.',
        'receta': {
            'Harina sin polvos de hornear': D('0.4'),
            'Huevos': D('6'),
            'Chocolate de cobertura semiamargo': D('0.35'),
        },
        'extras': ['Chocolate extra', 'Frambuesas extra', 'Frutillas frescas'],
    },
    {
        'nombre': 'Torta Tres Leches',
        'tiempo': 150,
        'categoria': 'torta',
        'precio': 32000,
        'descripcion': 'Bizcocho esponjoso bañado en tres leches y cubierto con crema chantilly. Rinde 15 porciones.',
        'receta': {
            'Harina sin polvos de hornear': D('0.25'),
            'Azúcar granulada': D('0.35'),
            'Huevos': D('8'),
            'Leche entera': D('0.5'),
            'Crema para batir': D('0.5'),
            'Leche condensada (lata 397 g)': D('1'),
            'Esencia de vainilla': D('10'),
            'Polvos de hornear': D('0.01'),
        },
        'extras': ['Frutillas frescas', 'Manjar extra', 'Crema chantilly extra'],
    },
    {
        'nombre': 'Torta Mil Hojas Manjar Nuez',
        'tiempo': 240,
        'categoria': 'torta',
        'precio': 38000,
        'descripcion': 'Capas de hojarasca crujiente con abundante manjar y nueces. Rinde 15 porciones.',
        'receta': {
            'Harina sin polvos de hornear': D('0.6'),
            'Mantequilla sin sal': D('0.35'),
            'Manjar': D('1.2'),
            'Nueces mariposa': D('0.2'),
            'Azúcar flor': D('0.05'),
        },
        'extras': ['Manjar extra', 'Nueces extra', 'Almendras laminadas'],
    },
    {
        'nombre': 'Torta Selva Negra',
        'tiempo': 210,
        'categoria': 'torta',
        'precio': 36000,
        'descripcion': 'Bizcocho de chocolate con crema, cerezas en almíbar y virutas de chocolate. Rinde 15 porciones.',
        'receta': {
            'Harina sin polvos de hornear': D('0.2'),
            'Cacao amargo en polvo': D('0.06'),
            'Azúcar granulada': D('0.3'),
            'Huevos': D('6'),
            'Crema para batir': D('0.6'),
            'Chocolate de cobertura semiamargo': D('0.15'),
            'Cerezas en almíbar': D('0.4'),
            'Mantequilla sin sal': D('0.05'),
        },
        'extras': ['Cerezas extra', 'Chocolate extra', 'Crema chantilly extra'],
    },
    {
        'nombre': 'Torta de Lúcuma Manjar',
        'tiempo': 180,
        'categoria': 'torta',
        'precio': 35000,
        'descripcion': 'Bizcocho de vainilla con crema de lúcuma y una capa de manjar. Rinde 15 porciones.',
        'receta': {
            'Harina sin polvos de hornear': D('0.25'),
            'Azúcar granulada': D('0.3'),
            'Huevos': D('6'),
            'Pulpa de lúcuma': D('0.5'),
            'Manjar': D('0.5'),
            'Crema para batir': D('0.4'),
        },
        'extras': ['Lúcuma extra', 'Manjar extra', 'Nueces extra'],
    },
    {
        'nombre': 'Cheesecake de Frambuesa',
        'tiempo': 300,
        'categoria': 'postre',
        'precio': 31000,
        'descripcion': 'Base de galleta, crema de queso horneada y cobertura de frambuesas. Rinde 12 porciones.',
        'receta': {
            'Galletas de vainilla': D('0.25'),
            'Mantequilla sin sal': D('0.1'),
            'Queso crema': D('0.6'),
            'Azúcar granulada': D('0.2'),
            'Huevos': D('3'),
            'Crema para batir': D('0.2'),
            'Frambuesas': D('0.3'),
        },
        'extras': ['Frambuesas extra', 'Arándanos', 'Frutillas frescas'],
    },
    {
        'nombre': 'Cupcakes Red Velvet (6 un)',
        'tiempo': 90,
        'categoria': 'cupcake',
        'precio': 11900,
        'descripcion': 'Seis cupcakes red velvet con frosting de queso crema.',
        'receta': {
            'Harina sin polvos de hornear': D('0.18'),
            'Cacao amargo en polvo': D('0.01'),
            'Azúcar granulada': D('0.15'),
            'Mantequilla sin sal': D('0.06'),
            'Huevos': D('2'),
            'Leche entera': D('0.12'),
            'Colorante rojo en gel': D('5'),
            'Queso crema': D('0.15'),
            'Azúcar flor': D('0.1'),
        },
        'extras': ['Frosting de queso crema extra', 'Granas de colores', 'Chocolate extra'],
    },
    {
        'nombre': 'Cupcakes Vainilla y Frutilla (6 un)',
        'tiempo': 75,
        'categoria': 'cupcake',
        'precio': 9900,
        'descripcion': 'Seis cupcakes de vainilla con crema y frutillas frescas.',
        'receta': {
            'Harina sin polvos de hornear': D('0.18'),
            'Azúcar granulada': D('0.15'),
            'Mantequilla sin sal': D('0.08'),
            'Huevos': D('2'),
            'Leche entera': D('0.1'),
            'Esencia de vainilla': D('5'),
            'Frutillas': D('0.15'),
            'Crema para batir': D('0.15'),
        },
        'extras': ['Frutillas frescas', 'Granas de colores', 'Arándanos'],
    },
    {
        'nombre': 'Pie de Limón',
        'tiempo': 150,
        'categoria': 'postre',
        'precio': 19900,
        'descripcion': 'Base de galleta, relleno cremoso de limón y merengue tostado. Rinde 10 porciones.',
        'receta': {
            'Galletas de vainilla': D('0.2'),
            'Mantequilla sin sal': D('0.08'),
            'Leche condensada (lata 397 g)': D('2'),
            'Limones': D('6'),
            'Huevos': D('4'),
            'Azúcar granulada': D('0.15'),
        },
        'extras': ['Merengue extra', 'Ralladura de limón extra', 'Coco rallado'],
    },
    {
        'nombre': 'Tiramisú (8 porciones)',
        'tiempo': 270,
        'categoria': 'postre',
        'precio': 26000,
        'descripcion': 'Capas de soletillas con café y crema de mascarpone, espolvoreado con cacao.',
        'receta': {
            'Queso mascarpone': D('0.5'),
            'Crema para batir': D('0.25'),
            'Azúcar granulada': D('0.12'),
            'Huevos': D('4'),
            'Bizcochos de soletilla': D('0.3'),
            'Café molido': D('0.03'),
            'Cacao amargo en polvo': D('0.02'),
        },
        'extras': ['Cacao extra', 'Café extra', 'Crema chantilly extra'],
    },
    {
        'nombre': 'Brownies con Nuez (caja 12 un)',
        'tiempo': 60,
        'categoria': 'postre',
        'precio': 15900,
        'descripcion': 'Doce brownies húmedos de chocolate semiamargo con nueces.',
        'receta': {
            'Chocolate de cobertura semiamargo': D('0.25'),
            'Mantequilla sin sal': D('0.2'),
            'Azúcar granulada': D('0.3'),
            'Huevos': D('4'),
            'Harina sin polvos de hornear': D('0.12'),
            'Nueces mariposa': D('0.12'),
        },
        'extras': ['Nueces extra', 'Chocolate extra', 'Crema de avellanas'],
    },
]


class Command(BaseCommand):
    help = 'Carga el catálogo de Dulce Arte: insumos, productos, recetas y extras.'

    @transaction.atomic
    def handle(self, *args, **options):
        insumos = {}
        nuevos = 0
        for nombre, (unidad, costo, stock, minimo) in INSUMOS.items():
            insumo, creado = Insumo.objects.get_or_create(
                nombre=nombre,
                defaults={'unidad': unidad, 'costo_unitario': costo, 'stock_actual': stock, 'stock_minimo': minimo},
            )
            if not creado:
                # Si ya existía, se respeta su stock actual (lo maneja la bodega).
                insumo.unidad = unidad
                insumo.costo_unitario = costo
                insumo.stock_minimo = minimo
                insumo.activo = True
                insumo.save()
            nuevos += creado
            insumos[nombre] = insumo
        self.stdout.write(self.style.SUCCESS(f'Insumos: {len(insumos)} ({nuevos} nuevos).'))

        productos = {}
        for datos in PRODUCTOS:
            producto, _ = Producto.objects.update_or_create(
                nombre=datos['nombre'],
                defaults={
                    'categoria': datos['categoria'],
                    'precio_base': datos['precio'],
                    'tiempo_preparacion': datos['tiempo'],
                    'descripcion': datos['descripcion'],
                    'activo': True,
                },
            )
            producto.receta.all().delete()
            for nombre_insumo, cantidad in datos['receta'].items():
                RecetaItem.objects.create(producto=producto, insumo=insumos[nombre_insumo], cantidad=cantidad)
            productos[datos['nombre']] = producto
        self.stdout.write(self.style.SUCCESS(f'Productos con receta: {len(productos)}.'))

        for nombre, (nombre_insumo, cantidad, precio) in EXTRAS.items():
            extra, _ = OpcionPersonalizacion.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'insumo': insumos[nombre_insumo],
                    'cantidad_por_porcion': cantidad,
                    'precio_por_porcion': precio,
                    'activo': True,
                },
            )
            extra.productos.set(
                [productos[d['nombre']] for d in PRODUCTOS if nombre in d['extras']]
            )
        self.stdout.write(self.style.SUCCESS(f'Extras: {len(EXTRAS)}, vinculados a sus productos.'))
        fotos = sum(
            self.asignar_foto(producto, 'productos', FOTOS_PRODUCTOS.get(nombre, slugify(nombre)))
            for nombre, producto in productos.items()
        )
        fotos += sum(
            self.asignar_foto(insumo, 'insumos', slugify(nombre)) for nombre, insumo in insumos.items()
        )
        self.stdout.write(self.style.SUCCESS(f'Fotos asignadas: {fotos}.'))
        self.stdout.write(self.style.SUCCESS('Catálogo de Dulce Arte cargado.'))

    def asignar_foto(self, objeto, carpeta, nombre_archivo):
        """Copia la foto de inventario/fotos/<carpeta>/ a media/ si el objeto aún no tiene imagen."""
        if objeto.imagen:
            return 0
        for extension in EXTENSIONES:
            ruta = CARPETA_FOTOS / carpeta / f'{nombre_archivo}{extension}'
            if ruta.exists():
                with ruta.open('rb') as archivo:
                    objeto.imagen.save(ruta.name, File(archivo), save=True)
                return 1
        return 0
