"""
Modelos de la app PEDIDOS.

- Cliente: quien encarga el pedido.
- Pedido: la cotización/pedido con su estado (flujo Kanban).
- DetallePedido: cada producto dentro del pedido.
- PersonalizacionDetalle: extras agregados o quitados a un producto del pedido.
- HistorialEstado: trazabilidad de cada cambio de estado.
"""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from inventario.models import OpcionPersonalizacion, Producto


class Cliente(models.Model):
    """Persona que encarga pedidos a la pastelería."""

    nombre = models.CharField('nombre completo', max_length=150)
    telefono = models.CharField('teléfono', max_length=20)
    email = models.EmailField('correo electrónico', blank=True)
    direccion = models.CharField('dirección', max_length=255, blank=True)
    creado_en = models.DateTimeField('creado en', auto_now_add=True)

    class Meta:
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.telefono})'


class Pedido(models.Model):
    """Cotización o pedido personalizado."""

    class Estado(models.TextChoices):
        COTIZACION = 'cotizacion', 'Cotización'
        RECIBIDO = 'recibido', 'Recibido'
        EN_PREPARACION = 'en_preparacion', 'En Preparación'
        HORNEADO_DECORADO = 'horneado_decorado', 'Horneado/Decorado'
        CONTROL_CALIDAD = 'control_calidad', 'Control de Calidad'
        LISTO = 'listo', 'Listo'
        EN_DESPACHO = 'en_despacho', 'En Despacho'
        ENTREGADO = 'entregado', 'Entregado'
        CANCELADO = 'cancelado', 'Cancelado'

    class TipoEntrega(models.TextChoices):
        RETIRO = 'retiro', 'Retiro en tienda'
        DESPACHO = 'despacho', 'Despacho a domicilio'

    # Columnas del tablero Kanban de cocina, en orden.
    ESTADOS_KANBAN = [
        Estado.RECIBIDO,
        Estado.EN_PREPARACION,
        Estado.HORNEADO_DECORADO,
        Estado.CONTROL_CALIDAD,
        Estado.LISTO,
    ]

    # Regla de negocio: los pedidos se hacen con al menos 24 horas de anticipación.
    ANTICIPACION_MINIMA = timedelta(hours=24)

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='pedidos',
        verbose_name='cliente',
    )
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.COTIZACION
    )
    tipo_entrega = models.CharField(
        'tipo de entrega',
        max_length=10,
        choices=TipoEntrega.choices,
        default=TipoEntrega.RETIRO,
    )
    fecha_entrega = models.DateTimeField('fecha y hora de entrega')
    direccion_entrega = models.CharField(
        'dirección de entrega',
        max_length=255,
        blank=True,
        help_text='Obligatoria si el pedido es con despacho a domicilio.',
    )
    diseno = models.TextField('descripción del diseño', blank=True)
    imagen_referencia = models.ImageField(
        'imagen de referencia del diseño', upload_to='pedidos/referencias/', blank=True
    )
    observaciones = models.TextField('observaciones', blank=True)
    total = models.PositiveIntegerField('total (CLP)', default=0)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_creados',
        verbose_name='registrado por',
    )
    creado_en = models.DateTimeField('creado en', auto_now_add=True)
    actualizado_en = models.DateTimeField('actualizado en', auto_now=True)

    class Meta:
        verbose_name = 'pedido'
        verbose_name_plural = 'pedidos'
        ordering = ['fecha_entrega']

    def __str__(self):
        return f'Pedido #{self.pk} - {self.cliente.nombre}'

    def clean(self):
        """Validaciones de negocio que se ejecutan en formularios y en el Admin."""
        errores = {}

        # La anticipación mínima solo se exige mientras el pedido es una cotización.
        if self.fecha_entrega and self.estado == self.Estado.COTIZACION:
            minimo = timezone.now() + self.ANTICIPACION_MINIMA
            if self.fecha_entrega < minimo:
                errores['fecha_entrega'] = (
                    'La entrega debe programarse con al menos 24 horas de anticipación.'
                )

        if self.tipo_entrega == self.TipoEntrega.DESPACHO and not self.direccion_entrega:
            errores['direccion_entrega'] = (
                'Debes indicar la dirección de entrega para pedidos con despacho.'
            )

        if errores:
            raise ValidationError(errores)

    def calcular_total(self, guardar=True):
        """Regla de negocio: el total se calcula a partir de los detalles."""
        self.total = sum(detalle.subtotal for detalle in self.detalles.all())
        if guardar:
            self.save(update_fields=['total', 'actualizado_en'])
        return self.total

    @property
    def en_kanban(self):
        return self.estado in self.ESTADOS_KANBAN


class DetallePedido(models.Model):
    """Un producto dentro de un pedido, con su cantidad y comentario."""

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='pedido',
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='detalles_pedido',
        verbose_name='producto',
    )
    cantidad = models.PositiveIntegerField(
        'cantidad', default=1, validators=[MinValueValidator(1)]
    )
    precio_unitario = models.PositiveIntegerField(
        'precio unitario (CLP)',
        default=0,
        help_text='Se copia automáticamente del precio base del producto.',
    )
    comentario = models.TextField(
        'comentario o añadido extra',
        blank=True,
        help_text='Peticiones que no estén en la lista de opciones.',
    )

    class Meta:
        verbose_name = 'detalle del pedido'
        verbose_name_plural = 'detalles del pedido'

    def __str__(self):
        return f'{self.cantidad} x {self.producto.nombre}'

    def save(self, *args, **kwargs):
        # Se guarda el precio del momento: si mañana cambia el precio del producto,
        # los pedidos antiguos conservan el valor con el que se cotizaron.
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_base
        super().save(*args, **kwargs)

    @property
    def total_personalizaciones(self):
        if not self.pk:
            return 0
        return sum(p.precio_adicional for p in self.personalizaciones.all())

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad + self.total_personalizaciones


class PersonalizacionDetalle(models.Model):
    """
    Extra elegido de la lista de opciones para un producto del pedido.
    porciones > 0  -> agregar más (se cobra).
    porciones < 0  -> quitar (no se cobra, consume menos insumo).
    Las porciones aplican a CADA unidad del producto.
    """

    detalle = models.ForeignKey(
        DetallePedido,
        on_delete=models.CASCADE,
        related_name='personalizaciones',
        verbose_name='detalle del pedido',
    )
    opcion = models.ForeignKey(
        OpcionPersonalizacion,
        on_delete=models.PROTECT,
        related_name='usos',
        verbose_name='opción',
    )
    porciones = models.IntegerField(
        'porciones',
        validators=[MinValueValidator(-5), MaxValueValidator(5)],
        help_text='Positivo = agregar más. Negativo = poner menos. Rango de -5 a 5.',
    )

    class Meta:
        verbose_name = 'personalización'
        verbose_name_plural = 'personalizaciones'
        constraints = [
            models.UniqueConstraint(
                fields=['detalle', 'opcion'], name='opcion_unica_por_detalle'
            )
        ]

    def __str__(self):
        signo = '+' if self.porciones > 0 else ''
        return f'{self.opcion.nombre} ({signo}{self.porciones})'

    def clean(self):
        if self.porciones == 0:
            raise ValidationError({'porciones': 'Las porciones no pueden ser 0.'})
        # Regla de negocio: cada producto solo acepta sus propios extras.
        if self.opcion_id and self.detalle_id:
            if not self.opcion.productos.filter(pk=self.detalle.producto_id).exists():
                raise ValidationError({
                    'opcion': f'"{self.opcion.nombre}" no está disponible para {self.detalle.producto.nombre}.'
                })

    @property
    def precio_adicional(self):
        """Solo se cobra cuando se agregan porciones."""
        if self.porciones <= 0:
            return 0
        return self.porciones * self.opcion.precio_por_porcion * self.detalle.cantidad


class HistorialEstado(models.Model):
    """Trazabilidad: guarda cada cambio de estado del pedido."""

    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='pedido',
    )
    estado_anterior = models.CharField(
        'estado anterior', max_length=20, choices=Pedido.Estado.choices, blank=True
    )
    estado_nuevo = models.CharField(
        'estado nuevo', max_length=20, choices=Pedido.Estado.choices
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cambios_estado',
        verbose_name='realizado por',
    )
    comentario = models.CharField('comentario', max_length=255, blank=True)
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'cambio de estado'
        verbose_name_plural = 'historial de estados'
        ordering = ['-fecha']

    def __str__(self):
        return (
            f'Pedido #{self.pedido_id}: '
            f'{self.get_estado_anterior_display() or "—"} → {self.get_estado_nuevo_display()}'
        )
