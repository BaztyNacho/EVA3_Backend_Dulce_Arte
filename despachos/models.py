"""
Modelos de la app DESPACHOS.

- Ruta: agrupa los despachos de un día/sector.
- Despacho: entrega de un pedido, confirmada con firma digital o foto de comprobante.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from pedidos.models import Pedido


class Ruta(models.Model):
    """Ruta de reparto que agrupa varios despachos."""

    class Estado(models.TextChoices):
        PLANIFICADA = 'planificada', 'Planificada'
        EN_CURSO = 'en_curso', 'En curso'
        FINALIZADA = 'finalizada', 'Finalizada'

    nombre = models.CharField('nombre', max_length=100, help_text='Ejemplo: Ruta Norte.')
    fecha = models.DateField('fecha de reparto')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rutas',
        verbose_name='repartidor responsable',
    )
    estado = models.CharField(
        'estado', max_length=12, choices=Estado.choices, default=Estado.PLANIFICADA
    )
    observaciones = models.TextField('observaciones', blank=True)
    creado_en = models.DateTimeField('creado en', auto_now_add=True)

    class Meta:
        verbose_name = 'ruta de despacho'
        verbose_name_plural = 'rutas de despacho'
        ordering = ['-fecha', 'nombre']

    def __str__(self):
        return f'{self.nombre} ({self.fecha:%d-%m-%Y})'


class Despacho(models.Model):
    """Entrega a domicilio de un pedido."""

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        EN_CAMINO = 'en_camino', 'En camino'
        ENTREGADO = 'entregado', 'Entregado'
        FALLIDO = 'fallido', 'Fallido'

    pedido = models.OneToOneField(
        Pedido,
        on_delete=models.PROTECT,
        related_name='despacho',
        verbose_name='pedido',
        limit_choices_to={'tipo_entrega': Pedido.TipoEntrega.DESPACHO},
    )
    ruta = models.ForeignKey(
        Ruta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='despachos',
        verbose_name='ruta',
    )
    orden = models.PositiveSmallIntegerField(
        'orden en la ruta', default=1, help_text='Posición de la parada dentro de la ruta.'
    )
    estado = models.CharField(
        'estado', max_length=10, choices=Estado.choices, default=Estado.PENDIENTE
    )
    firma = models.ImageField('firma digital', upload_to='despachos/firmas/', blank=True)
    comprobante = models.ImageField(
        'foto del comprobante', upload_to='despachos/comprobantes/', blank=True
    )
    nombre_receptor = models.CharField('nombre de quien recibe', max_length=150, blank=True)
    fecha_entrega_real = models.DateTimeField('fecha real de entrega', null=True, blank=True)
    observaciones = models.TextField('observaciones', blank=True)

    class Meta:
        verbose_name = 'despacho'
        verbose_name_plural = 'despachos'
        ordering = ['ruta', 'orden']

    def __str__(self):
        return f'Despacho del pedido #{self.pedido_id} ({self.get_estado_display()})'

    def clean(self):
        errores = {}

        if self.pedido_id and self.pedido.tipo_entrega != Pedido.TipoEntrega.DESPACHO:
            errores['pedido'] = 'Este pedido es para retiro en tienda, no requiere despacho.'

        # Regla de negocio: para confirmar la entrega se exige evidencia.
        if self.estado == self.Estado.ENTREGADO:
            if not self.firma and not self.comprobante:
                errores['estado'] = (
                    'Para marcar como entregado se requiere la firma o la foto del comprobante.'
                )
            if not self.nombre_receptor:
                errores['nombre_receptor'] = 'Indica el nombre de quien recibe el pedido.'

        if errores:
            raise ValidationError(errores)