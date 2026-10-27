"""
Lógica de negocio de los DESPACHOS.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from pedidos.models import Pedido
from pedidos.services import ReglaNegocioError, registrar_cambio

from .models import Despacho


def marcar_pedido_entregado(despacho, usuario):
    """Cuando un despacho se entrega, el pedido también pasa a Entregado (con historial)."""
    pedido = despacho.pedido
    if pedido.estado == Pedido.Estado.ENTREGADO:
        return
    estado_anterior = pedido.estado
    pedido.estado = Pedido.Estado.ENTREGADO
    pedido.save(update_fields=['estado', 'actualizado_en'])
    registrar_cambio(pedido, estado_anterior, usuario, f'Entregado a {despacho.nombre_receptor}')


@transaction.atomic
def confirmar_entrega(despacho, usuario, nombre_receptor, firma=None, comprobante=None, observaciones=''):
    """
    Confirma la entrega de un despacho.
    Regla de negocio: se exige el nombre de quien recibe y la firma o la foto del comprobante.
    """
    despacho = Despacho.objects.select_for_update().select_related('pedido').get(pk=despacho.pk)
    if despacho.estado == Despacho.Estado.ENTREGADO:
        raise ReglaNegocioError(f'El despacho del pedido #{despacho.pedido_id} ya fue entregado.')

    despacho.nombre_receptor = nombre_receptor
    if firma:
        despacho.firma = firma
    if comprobante:
        despacho.comprobante = comprobante
    if observaciones:
        despacho.observaciones = observaciones
    despacho.estado = Despacho.Estado.ENTREGADO
    despacho.fecha_entrega_real = timezone.now()

    try:
        despacho.full_clean()
    except ValidationError as error:
        mensajes = [m for lista in error.message_dict.values() for m in lista]
        raise ReglaNegocioError(' '.join(mensajes))

    despacho.save()
    marcar_pedido_entregado(despacho, usuario)
    return despacho
