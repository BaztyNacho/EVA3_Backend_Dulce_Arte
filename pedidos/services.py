"""
Lógica de negocio de los pedidos (capa de "servicios").

Aquí se concentran las reglas del caso Dulce Arte para que se apliquen igual
desde el Django Admin, desde la API y desde las vistas web:

1. Confirmar una cotización: verifica stock según receta (BOM) y personalizaciones,
   descuenta los insumos y registra los movimientos.
2. Avanzar en el Kanban solo en orden.
3. Rechazar en Control de Calidad (vuelve a En Preparación).
4. Cancelar un pedido, devolviendo los insumos si aún no se empezó a preparar.

Todas las operaciones quedan registradas en el historial (trazabilidad).
"""

from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from inventario.models import Insumo, MovimientoInsumo

from .models import HistorialEstado, Pedido


class ReglaNegocioError(Exception):
    """Error que se lanza cuando una operación no cumple las reglas del negocio."""


# Orden del flujo de cocina: cada estado y el que le sigue.
SIGUIENTE_ESTADO = {
    Pedido.Estado.RECIBIDO: Pedido.Estado.EN_PREPARACION,
    Pedido.Estado.EN_PREPARACION: Pedido.Estado.HORNEADO_DECORADO,
    Pedido.Estado.HORNEADO_DECORADO: Pedido.Estado.CONTROL_CALIDAD,
    Pedido.Estado.CONTROL_CALIDAD: Pedido.Estado.LISTO,
}


def registrar_cambio(pedido, estado_anterior, usuario, comentario=''):
    """Guarda el cambio de estado en el historial del pedido."""
    HistorialEstado.objects.create(
        pedido=pedido,
        estado_anterior=estado_anterior,
        estado_nuevo=pedido.estado,
        usuario=usuario,
        comentario=comentario,
    )


def calcular_requerimientos(pedido):
    """
    Calcula cuánto de cada insumo necesita el pedido completo.

    Para cada producto del pedido:
      receta (cantidad por unidad) x cantidad de productos
      + personalizaciones (porciones x cantidad por porción x cantidad de productos)

    Devuelve un diccionario {insumo_id: cantidad_total}.
    """
    total = defaultdict(Decimal)
    detalles = pedido.detalles.prefetch_related(
        'producto__receta', 'personalizaciones__opcion'
    )
    for detalle in detalles:
        por_detalle = defaultdict(Decimal)
        for item in detalle.producto.receta.all():
            por_detalle[item.insumo_id] += item.cantidad * detalle.cantidad
        for perso in detalle.personalizaciones.all():
            por_detalle[perso.opcion.insumo_id] += (
                perso.porciones * perso.opcion.cantidad_por_porcion * detalle.cantidad
            )
        # Si el cliente pidió "menos" de algo, el consumo nunca puede quedar negativo.
        for insumo_id, cantidad in por_detalle.items():
            if cantidad > 0:
                total[insumo_id] += cantidad
    return dict(total)


@transaction.atomic
def confirmar_cotizacion(pedido, usuario):
    """
    Convierte una cotización en pedido: verifica stock, descuenta insumos
    y lo envía a la primera columna del Kanban (Recibido).
    """
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)

    if pedido.estado != Pedido.Estado.COTIZACION:
        raise ReglaNegocioError(
            f'El pedido #{pedido.pk} ya no es una cotización '
            f'(estado actual: {pedido.get_estado_display()}).'
        )
    if not pedido.detalles.exists():
        raise ReglaNegocioError(f'El pedido #{pedido.pk} no tiene productos.')

    requerimientos = calcular_requerimientos(pedido)

    # Bloqueamos los insumos para que dos confirmaciones simultáneas no descuenten de más.
    insumos = Insumo.objects.select_for_update().in_bulk(list(requerimientos))

    faltantes = []
    for insumo_id, necesario in requerimientos.items():
        insumo = insumos[insumo_id]
        if insumo.stock_actual < necesario:
            faltante = necesario - insumo.stock_actual
            faltantes.append(f'{insumo.nombre} (faltan {faltante.normalize()} {insumo.unidad})')
    if faltantes:
        raise ReglaNegocioError(
            f'No hay stock suficiente para el pedido #{pedido.pk}: ' + ', '.join(faltantes) + '.'
        )

    for insumo_id, necesario in requerimientos.items():
        insumo = insumos[insumo_id]
        insumo.stock_actual -= necesario
        insumo.save(update_fields=['stock_actual', 'actualizado_en'])
        MovimientoInsumo.objects.create(
            insumo=insumo,
            tipo=MovimientoInsumo.Tipo.SALIDA,
            cantidad=necesario,
            motivo=f'Consumo por pedido #{pedido.pk}',
            pedido=pedido,
            usuario=usuario,
        )

    estado_anterior = pedido.estado
    pedido.estado = Pedido.Estado.RECIBIDO
    pedido.calcular_total(guardar=False)
    pedido.save(update_fields=['estado', 'total', 'actualizado_en'])
    registrar_cambio(pedido, estado_anterior, usuario, 'Cotización confirmada; insumos descontados')

    # Devolvemos los insumos que quedaron con stock bajo, para poder avisar.
    return [insumo for insumo in insumos.values() if insumo.stock_bajo]


@transaction.atomic
def avanzar_estado(pedido, usuario):
    """Mueve el pedido a la siguiente columna del Kanban (sin saltarse pasos)."""
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    estado_anterior = pedido.estado

    if pedido.estado in SIGUIENTE_ESTADO:
        pedido.estado = SIGUIENTE_ESTADO[pedido.estado]
        comentario = ''
    elif pedido.estado == Pedido.Estado.LISTO:
        if pedido.tipo_entrega == Pedido.TipoEntrega.DESPACHO:
            from despachos.models import Despacho  # import aquí para evitar import circular

            pedido.estado = Pedido.Estado.EN_DESPACHO
            Despacho.objects.get_or_create(pedido=pedido)
            comentario = 'Enviado a despacho'
        else:
            pedido.estado = Pedido.Estado.ENTREGADO
            comentario = 'Retirado en tienda'
    elif pedido.estado == Pedido.Estado.COTIZACION:
        raise ReglaNegocioError(
            f'El pedido #{pedido.pk} es una cotización: primero debe confirmarse.'
        )
    elif pedido.estado == Pedido.Estado.EN_DESPACHO:
        raise ReglaNegocioError(
            f'El pedido #{pedido.pk} está en despacho: se marca como entregado '
            'al confirmar la entrega con firma o comprobante.'
        )
    else:
        raise ReglaNegocioError(
            f'El pedido #{pedido.pk} está {pedido.get_estado_display().lower()} y no puede avanzar.'
        )

    pedido.save(update_fields=['estado', 'actualizado_en'])
    registrar_cambio(pedido, estado_anterior, usuario, comentario)
    return pedido


@transaction.atomic
def rechazar_control_calidad(pedido, usuario, motivo=''):
    """Si el producto no pasa el control de calidad, vuelve a En Preparación."""
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if pedido.estado != Pedido.Estado.CONTROL_CALIDAD:
        raise ReglaNegocioError(
            f'El pedido #{pedido.pk} no está en Control de Calidad.'
        )
    estado_anterior = pedido.estado
    pedido.estado = Pedido.Estado.EN_PREPARACION
    pedido.save(update_fields=['estado', 'actualizado_en'])
    registrar_cambio(pedido, estado_anterior, usuario, motivo or 'Rechazado en control de calidad')
    return pedido


@transaction.atomic
def cancelar_pedido(pedido, usuario, motivo=''):
    """
    Cancela un pedido.
    - Si estaba en Recibido (aún no se empieza a preparar), los insumos vuelven a bodega.
    - Si ya estaba en preparación, los insumos se consideran consumidos.
    - No se puede cancelar un pedido en despacho, entregado o ya cancelado.
    """
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    no_cancelables = [
        Pedido.Estado.EN_DESPACHO,
        Pedido.Estado.ENTREGADO,
        Pedido.Estado.CANCELADO,
    ]
    if pedido.estado in no_cancelables:
        raise ReglaNegocioError(
            f'El pedido #{pedido.pk} está {pedido.get_estado_display().lower()} y no se puede cancelar.'
        )

    insumos_devueltos = False
    if pedido.estado == Pedido.Estado.RECIBIDO:
        salidas = pedido.movimientos_insumo.filter(tipo=MovimientoInsumo.Tipo.SALIDA)
        for salida in salidas.select_related('insumo'):
            insumo = Insumo.objects.select_for_update().get(pk=salida.insumo_id)
            insumo.stock_actual += salida.cantidad
            insumo.save(update_fields=['stock_actual', 'actualizado_en'])
            MovimientoInsumo.objects.create(
                insumo=insumo,
                tipo=MovimientoInsumo.Tipo.DEVOLUCION,
                cantidad=salida.cantidad,
                motivo=f'Devolución por cancelación del pedido #{pedido.pk}',
                pedido=pedido,
                usuario=usuario,
            )
            insumos_devueltos = True

    estado_anterior = pedido.estado
    pedido.estado = Pedido.Estado.CANCELADO
    pedido.save(update_fields=['estado', 'actualizado_en'])
    comentario = motivo or 'Pedido cancelado'
    if insumos_devueltos:
        comentario += ' (insumos devueltos a bodega)'
    registrar_cambio(pedido, estado_anterior, usuario, comentario)
    return insumos_devueltos