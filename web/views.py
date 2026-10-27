"""
Vistas de la interfaz web de Dulce Arte.

Las páginas se generan con templates de Django. Las acciones (crear cotización,
confirmar, avanzar en el Kanban, etc.) las hace JavaScript llamando a la API,
que aplica las mismas reglas de negocio que el Admin.
"""

from datetime import timedelta
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from despachos.models import Despacho, Ruta
from inventario.models import Insumo, MovimientoInsumo, OpcionPersonalizacion, Producto
from pedidos.models import Pedido
from pedidos.permisos import es_administrador, es_ventas


def rol_requerido(*, solo_admin=False, solo_ventas=False):
    """
    Permite el acceso solo a usuarios con rol.
    solo_admin=True  -> solo el Administrador.
    solo_ventas=True -> solo Atención y Ventas.
    """

    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            usuario = request.user
            if solo_admin and not es_administrador(usuario):
                raise PermissionDenied
            if solo_ventas and not es_ventas(usuario):
                raise PermissionDenied
            if not (es_administrador(usuario) or es_ventas(usuario)):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


@rol_requerido()
def inicio(request):
    ahora = timezone.localtime()
    hoy = ahora.date()
    pedidos_activos = Pedido.objects.exclude(
        estado__in=[Pedido.Estado.ENTREGADO, Pedido.Estado.CANCELADO]
    ).select_related('cliente').prefetch_related('detalles__producto')

    entregas_proximas = pedidos_activos.exclude(estado=Pedido.Estado.COTIZACION).filter(
        fecha_entrega__date__lte=hoy + timedelta(days=1)
    ).order_by('fecha_entrega')[:8]

    contexto = {
        'cotizaciones': pedidos_activos.filter(estado=Pedido.Estado.COTIZACION).count(),
        'en_cocina': pedidos_activos.filter(estado__in=Pedido.ESTADOS_KANBAN).exclude(
            estado=Pedido.Estado.LISTO
        ).count(),
        'listos': pedidos_activos.filter(estado=Pedido.Estado.LISTO).count(),
        'entregas_hoy': pedidos_activos.filter(fecha_entrega__date=hoy).exclude(
            estado=Pedido.Estado.COTIZACION
        ).count(),
        'entregas_proximas': entregas_proximas,
        'limite_urgente': ahora + timedelta(hours=3),
    }
    if es_administrador(request.user):
        contexto['insumos_bajos'] = Insumo.objects.filter(
            activo=True, stock_actual__lte=F('stock_minimo')
        )
    return render(request, 'web/inicio.html', contexto)


FILTROS_ESTADO = [
    ('activos', 'Activos'),
    ('cotizacion', 'Cotizaciones'),
    ('cocina', 'En cocina'),
    ('listo', 'Listos'),
    ('en_despacho', 'En despacho'),
    ('entregado', 'Entregados'),
    ('cancelado', 'Cancelados'),
]


@rol_requerido()
def pedidos_lista(request):
    filtro = request.GET.get('estado', 'activos')
    texto = request.GET.get('q', '').strip()

    pedidos = Pedido.objects.select_related('cliente').prefetch_related('detalles__producto')
    if filtro == 'activos':
        pedidos = pedidos.exclude(estado__in=[Pedido.Estado.ENTREGADO, Pedido.Estado.CANCELADO])
    elif filtro == 'cocina':
        pedidos = pedidos.filter(estado__in=Pedido.ESTADOS_KANBAN).exclude(estado=Pedido.Estado.LISTO)
    elif filtro in Pedido.Estado.values:
        pedidos = pedidos.filter(estado=filtro)

    if texto:
        condicion = Q(cliente__nombre__icontains=texto) | Q(cliente__telefono__icontains=texto)
        if texto.lstrip('#').isdigit():
            condicion |= Q(pk=int(texto.lstrip('#')))
        pedidos = pedidos.filter(condicion)

    orden = '-fecha_entrega' if filtro in ('entregado', 'cancelado') else 'fecha_entrega'
    pagina = Paginator(pedidos.order_by(orden), 24).get_page(request.GET.get('pagina'))
    return render(request, 'web/pedidos_lista.html', {
        'pagina': pagina,
        'filtros': FILTROS_ESTADO,
        'filtro_actual': filtro,
        'texto': texto,
        'limite_urgente': timezone.now() + timedelta(hours=3),
    })


@rol_requerido(solo_ventas=True)
def catalogo(request):
    """Catálogo para atender a clientes: productos disponibles con sus detalles."""
    categoria = request.GET.get('categoria', '')
    productos = (
        Producto.objects.filter(activo=True)
        .prefetch_related('receta__insumo', 'opciones')
        .order_by('categoria', 'nombre')
    )
    if categoria in Producto.Categoria.values:
        productos = productos.filter(categoria=categoria)
    categorias_con_productos = set(
        Producto.objects.filter(activo=True).values_list('categoria', flat=True)
    )
    return render(request, 'web/catalogo.html', {
        'productos': productos,
        'categorias': [c for c in Producto.Categoria.choices if c[0] in categorias_con_productos],
        'categoria_actual': categoria,
    })


@rol_requerido()
def pedido_nuevo(request):
    productos = Producto.objects.filter(activo=True).prefetch_related('opciones').order_by('categoria', 'nombre')
    opciones = OpcionPersonalizacion.objects.filter(activo=True)
    fecha_minima = timezone.localtime() + Pedido.ANTICIPACION_MINIMA + timedelta(minutes=5)
    return render(request, 'web/pedido_nuevo.html', {
        'productos_json': [
            {
                'id': p.pk,
                'nombre': p.nombre,
                'categoria': p.get_categoria_display(),
                'precio': p.precio_base,
                'imagen': p.imagen.url if p.imagen else '',
                'opciones': [o.pk for o in p.opciones.all() if o.activo],
            }
            for p in productos
        ],
        'opciones_json': [
            {'id': o.pk, 'nombre': o.nombre, 'precio': o.precio_por_porcion} for o in opciones
        ],
        'fecha_minima': fecha_minima.strftime('%Y-%m-%dT%H:%M'),
    })


@rol_requerido()
def pedido_detalle(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'creado_por').prefetch_related(
            'detalles__producto', 'detalles__personalizaciones__opcion', 'historial__usuario'
        ),
        pk=pk,
    )
    return render(request, 'web/pedido_detalle.html', {
        'pedido': pedido,
        'es_cotizacion': pedido.estado == Pedido.Estado.COTIZACION,
        'puede_cancelar': es_administrador(request.user)
        and pedido.estado not in [Pedido.Estado.EN_DESPACHO, Pedido.Estado.ENTREGADO, Pedido.Estado.CANCELADO],
    })


# ---------------------------------------------------------------
# Vistas del Administrador: cocina, bodega y despachos
# ---------------------------------------------------------------
@rol_requerido(solo_admin=True)
def kanban(request):
    """Tablero de cocina. Las tarjetas se cargan y mueven con JavaScript usando la API."""
    columnas = [(estado, Pedido.Estado(estado).label) for estado in Pedido.ESTADOS_KANBAN]
    return render(request, 'web/kanban.html', {'columnas': columnas})


@rol_requerido(solo_admin=True)
def bodega(request):
    solo_bajo = request.GET.get('stock') == 'bajo'
    insumos = Insumo.objects.filter(activo=True).order_by('nombre')
    if solo_bajo:
        insumos = insumos.filter(stock_actual__lte=F('stock_minimo'))

    # Para la barra de cada insumo: la escala es 3 veces el stock mínimo
    # (o el stock actual, si es mayor). La marca indica dónde está el mínimo.
    insumos = list(insumos)
    for insumo in insumos:
        escala = max(insumo.stock_minimo * 3, insumo.stock_actual, 1)
        insumo.porcentaje_barra = round(insumo.stock_actual / escala * 100)
        insumo.porcentaje_minimo = round(insumo.stock_minimo / escala * 100)

    return render(request, 'web/bodega.html', {
        'insumos': insumos,
        'solo_bajo': solo_bajo,
        'total_bajo': Insumo.objects.filter(activo=True, stock_actual__lte=F('stock_minimo')).count(),
        'movimientos': MovimientoInsumo.objects.select_related('insumo', 'usuario', 'pedido')[:8],
        'tipos': MovimientoInsumo.Tipo.choices,
    })


@rol_requerido(solo_admin=True)
def despachos(request):
    hoy = timezone.localdate()
    activos = Despacho.objects.exclude(estado=Despacho.Estado.ENTREGADO).select_related(
        'pedido__cliente', 'ruta'
    ).order_by('pedido__fecha_entrega')
    return render(request, 'web/despachos.html', {
        'sin_ruta': activos.filter(ruta__isnull=True),
        'rutas': Ruta.objects.exclude(estado=Ruta.Estado.FINALIZADA).prefetch_related(
            'despachos__pedido__cliente'
        ).order_by('fecha', 'nombre'),
        'entregados_hoy': Despacho.objects.filter(
            estado=Despacho.Estado.ENTREGADO, fecha_entrega_real__date=hoy
        ).select_related('pedido__cliente'),
        'hoy': hoy,
    })


@rol_requerido(solo_admin=True)
def despacho_entrega(request, pk):
    despacho = get_object_or_404(
        Despacho.objects.select_related('pedido__cliente', 'ruta').prefetch_related(
            'pedido__detalles__producto'
        ),
        pk=pk,
    )
    return render(request, 'web/despacho_entrega.html', {'despacho': despacho})
