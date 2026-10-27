"""
Modelos de la app INVENTARIO.

Aquí vive todo lo relacionado con la bodega y el catálogo:
- Insumo: materias primas (harina, huevos, chocolate...).
- Producto: lo que vende la pastelería (tortas, cupcakes...).
- RecetaItem: la Lista de Materiales (BOM) de cada producto.
- OpcionPersonalizacion: extras que el cliente puede agregar o quitar.
- MovimientoInsumo: registro de cada entrada o salida de bodega.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Insumo(models.Model):
    """Materia prima almacenada en bodega."""

    class Unidad(models.TextChoices):
        KILOGRAMO = 'kg', 'Kilogramos'
        GRAMO = 'g', 'Gramos'
        LITRO = 'l', 'Litros'
        MILILITRO = 'ml', 'Mililitros'
        UNIDAD = 'un', 'Unidades'

    nombre = models.CharField('nombre', max_length=100, unique=True)
    unidad = models.CharField('unidad de medida', max_length=2, choices=Unidad.choices)
    stock_actual = models.DecimalField(
        'stock actual',
        max_digits=10,
        decimal_places=3,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    stock_minimo = models.DecimalField(
        'stock mínimo',
        max_digits=10,
        decimal_places=3,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Cuando el stock llegue a este valor se mostrará una alerta.',
    )
    costo_unitario = models.PositiveIntegerField(
        'costo por unidad (CLP)',
        default=0,
        help_text='Costo en pesos chilenos por cada unidad de medida.',
    )
    imagen = models.ImageField('imagen', upload_to='insumos/', blank=True)
    activo = models.BooleanField('activo', default=True)
    creado_en = models.DateTimeField('creado en', auto_now_add=True)
    actualizado_en = models.DateTimeField('actualizado en', auto_now=True)

    class Meta:
        verbose_name = 'insumo'
        verbose_name_plural = 'insumos'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.get_unidad_display()})'

    @property
    def stock_bajo(self):
        """Regla de negocio: alerta cuando el stock llega al mínimo."""
        return self.stock_actual <= self.stock_minimo


class Producto(models.Model):
    """Producto del catálogo de la pastelería."""

    class Categoria(models.TextChoices):
        TORTA = 'torta', 'Torta'
        CUPCAKE = 'cupcake', 'Cupcake'
        GALLETA = 'galleta', 'Galleta'
        POSTRE = 'postre', 'Postre'
        OTRO = 'otro', 'Otro'

    nombre = models.CharField('nombre', max_length=120, unique=True)
    categoria = models.CharField(
        'categoría', max_length=10, choices=Categoria.choices, default=Categoria.TORTA
    )
    descripcion = models.TextField('descripción', blank=True)
    precio_base = models.PositiveIntegerField('precio base (CLP)')
    tiempo_preparacion = models.PositiveIntegerField(
        'tiempo de preparación (minutos)',
        default=0,
        help_text='Tiempo aproximado que toma elaborar una unidad. Es informativo.',
    )
    imagen = models.ImageField('imagen', upload_to='productos/', blank=True)
    activo = models.BooleanField('activo', default=True)
    creado_en = models.DateTimeField('creado en', auto_now_add=True)
    actualizado_en = models.DateTimeField('actualizado en', auto_now=True)

    class Meta:
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
        ordering = ['categoria', 'nombre']

    def __str__(self):
        return self.nombre

    @property
    def tiempo_legible(self):
        """Tiempo de preparación en texto: 210 -> "3 h 30 min"."""
        horas, minutos = divmod(self.tiempo_preparacion, 60)
        if horas and minutos:
            return f'{horas} h {minutos} min'
        if horas:
            return f'{horas} h'
        return f'{minutos} min'


class RecetaItem(models.Model):
    """
    Lista de Materiales (BOM): cuánto de cada insumo usa UNA unidad del producto.
    Ejemplo: 1 Torta de Chocolate usa 0,500 kg de harina.
    """

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='receta',
        verbose_name='producto',
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name='usos_en_recetas',
        verbose_name='insumo',
    )
    cantidad = models.DecimalField(
        'cantidad por unidad',
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )

    class Meta:
        verbose_name = 'ítem de receta'
        verbose_name_plural = 'receta (lista de materiales)'
        constraints = [
            models.UniqueConstraint(
                fields=['producto', 'insumo'], name='receta_insumo_unico_por_producto'
            )
        ]

    def __str__(self):
        return f'{self.producto}: {self.cantidad} {self.insumo.unidad} de {self.insumo.nombre}'


class OpcionPersonalizacion(models.Model):
    """
    Extra que el cliente puede agregar (más porciones) o quitar (menos porciones).
    Ejemplo: "Frutillas" = 0,100 kg de frutilla por porción, $1.500 por porción.
    Cada opción se ofrece solo en los productos indicados.
    """

    nombre = models.CharField('nombre', max_length=100, unique=True)
    productos = models.ManyToManyField(
        Producto,
        related_name='opciones',
        blank=True,
        verbose_name='productos donde se ofrece',
        help_text='La opción solo aparece en el cotizador para estos productos.',
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name='opciones_personalizacion',
        verbose_name='insumo que utiliza',
    )
    cantidad_por_porcion = models.DecimalField(
        'cantidad de insumo por porción',
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    precio_por_porcion = models.PositiveIntegerField(
        'precio por porción extra (CLP)',
        default=0,
        help_text='Se cobra solo cuando se agregan porciones (no al quitar).',
    )
    activo = models.BooleanField('activo', default=True)

    class Meta:
        verbose_name = 'opción de personalización'
        verbose_name_plural = 'opciones de personalización'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class MovimientoInsumo(models.Model):
    """Registro (trazabilidad) de cada entrada o salida de bodega."""

    class Tipo(models.TextChoices):
        ENTRADA = 'entrada', 'Entrada (compra o reposición)'
        SALIDA = 'salida', 'Salida (consumo por pedido)'
        DEVOLUCION = 'devolucion', 'Devolución (pedido cancelado)'
        AJUSTE = 'ajuste', 'Ajuste manual (merma o corrección)'

    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name='movimientos',
        verbose_name='insumo',
    )
    tipo = models.CharField('tipo', max_length=10, choices=Tipo.choices)
    cantidad = models.DecimalField(
        'cantidad',
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    motivo = models.CharField('motivo', max_length=200, blank=True)
    pedido = models.ForeignKey(
        'pedidos.Pedido',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_insumo',
        verbose_name='pedido asociado',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_insumo',
        verbose_name='registrado por',
    )
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'movimiento de insumo'
        verbose_name_plural = 'movimientos de insumos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.cantidad} {self.insumo.unidad} de {self.insumo.nombre}'
