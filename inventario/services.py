"""
Lógica de negocio de la bodega (inventario).
"""

from django.db import transaction

from pedidos.services import ReglaNegocioError

from .models import Insumo, MovimientoInsumo

TIPOS_QUE_SUMAN = (MovimientoInsumo.Tipo.ENTRADA, MovimientoInsumo.Tipo.DEVOLUCION)


@transaction.atomic
def registrar_movimiento(insumo, tipo, cantidad, usuario, motivo='', pedido=None):
    """
    Registra una entrada o salida de bodega y actualiza el stock.
    Entrada y Devolución suman. Salida y Ajuste (merma) restan.
    El stock nunca puede quedar negativo.
    """
    if cantidad <= 0:
        raise ReglaNegocioError('La cantidad debe ser mayor que cero.')

    insumo = Insumo.objects.select_for_update().get(pk=insumo.pk)
    if tipo in TIPOS_QUE_SUMAN:
        insumo.stock_actual += cantidad
    else:
        if cantidad > insumo.stock_actual:
            raise ReglaNegocioError(
                f'No hay stock suficiente de {insumo.nombre}: '
                f'hay {insumo.stock_actual} {insumo.unidad} y se intenta descontar {cantidad}.'
            )
        insumo.stock_actual -= cantidad
    insumo.save(update_fields=['stock_actual', 'actualizado_en'])

    movimiento = MovimientoInsumo.objects.create(
        insumo=insumo,
        tipo=tipo,
        cantidad=cantidad,
        motivo=motivo,
        pedido=pedido,
        usuario=usuario,
    )
    return movimiento
