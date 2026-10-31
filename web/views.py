"""
Vistas de la interfaz web de Dulce Arte.

Las páginas se generan con templates de Django. Las acciones (crear cotización,
confirmar, avanzar en el Kanban, etc.) las hace JavaScript llamando a la API,
que aplica las mismas reglas de negocio que el Admin.
"""

import time
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from despachos.models import Despacho, Ruta
from inventario.models import Insumo, MovimientoInsumo, OpcionPersonalizacion, Producto
from pedidos.models import Pedido
from pedidos.permisos import es_administrador, es_ventas, rol_principal, roles_de
from web.middleware import CLAVE_SESION, DURACION_SEGUNDOS


def rol_requerido(*roles, incluir_admin=True):
    """
    Permite entrar solo a los roles indicados. Ejemplos:
      @rol_requerido()                      -> cualquier usuario con rol
      @rol_requerido('cocina')              -> Cocina (y el Administrador)
      @rol_requerido('ventas', incluir_admin=False) -> solo Atención y Ventas
    """

    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            roles_usuario = roles_de(request.user)
            permitidos = set(roles) | ({'admin'} if incluir_admin else set())
            if not roles_usuario:
                raise PermissionDenied          # usuario sin ningún rol
            if roles and not (roles_usuario & permitidos):
                raise PermissionDenied          # su rol no puede ver esta página
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


@rol_requerido()
def inicio(request):
    """Cada rol tiene su propia pantalla de inicio con lo que necesita su puesto."""
    rol = rol_principal(request.user)
    if rol == 'cocina':
        return inicio_cocina(request)
    if rol == 'bodega':
        return inicio_bodega(request)
    if rol == 'repartidor':
        return inicio_repartidor(request)

    ahora = timezone.localtime()
    hoy = ahora.date()
    pedidos_activos = Pedido.objects.exclude(
        estado__in=[Pedido.Estado.ENTREGADO, Pedido.Estado.CANCELADO]
    ).select_related('cliente').prefetch_related('detalles__producto')

    # Todos los pedidos confirmados que faltan por entregar, del más próximo al más lejano.
    # La columna izquierda muestra los 3 primeros; la ventana "Próximas entregas", todos.
    entregas_proximas = list(
        pedidos_activos.exclude(estado=Pedido.Estado.COTIZACION).order_by('fecha_entrega')
    )

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


def inicio_cocina(request):
    ahora = timezone.localtime()
    en_cocina = Pedido.objects.filter(estado__in=Pedido.ESTADOS_KANBAN).select_related(
        'cliente'
    ).prefetch_related('detalles__producto')
    limite_urgente = ahora + timedelta(hours=3)
    conteo = {estado: 0 for estado in Pedido.ESTADOS_KANBAN}
    for pedido in en_cocina:
        conteo[pedido.estado] += 1
    return render(request, 'web/inicio_cocina.html', {
        # Urgentes: aún en preparación (no listos) y con entrega en menos de 3 horas
        'urgentes': en_cocina.exclude(estado=Pedido.Estado.LISTO).filter(
            fecha_entrega__lte=limite_urgente
        ).order_by('fecha_entrega'),
        'etapas': [(estado, Pedido.Estado(estado).label, conteo[estado]) for estado in Pedido.ESTADOS_KANBAN],
        'para_manana': en_cocina.filter(fecha_entrega__date=ahora.date() + timedelta(days=1)).count(),
        'limite_urgente': limite_urgente,
    })


def inicio_bodega(request):
    hoy = timezone.localdate()
    activos = Insumo.objects.filter(activo=True)
    # Reponer pronto: bajo el mínimo o a menos de un 25 % por sobre él
    reponer = [i for i in activos.order_by('nombre') if i.stock_actual <= i.stock_minimo * Decimal('1.25')]
    reponer.sort(key=lambda i: (not i.stock_bajo, i.nombre))
    movimientos_hoy = MovimientoInsumo.objects.filter(fecha__date=hoy)
    return render(request, 'web/inicio_bodega.html', {
        'reponer': reponer,
        'bajo_minimo': sum(1 for i in reponer if i.stock_bajo),
        'insumos_activos': activos.count(),
        'movimientos_hoy': movimientos_hoy.count(),
        'pedidos_hoy': movimientos_hoy.filter(pedido__isnull=False).values('pedido').distinct().count(),
    })


def ruta_del_dia():
    """La ruta en curso o, si no hay, la próxima planificada (de hoy o atrasada)."""
    hoy = timezone.localdate()
    abiertas = Ruta.objects.filter(fecha__lte=hoy).exclude(estado=Ruta.Estado.FINALIZADA)
    return (
        abiertas.filter(estado=Ruta.Estado.EN_CURSO).order_by('fecha').first()
        or abiertas.filter(estado=Ruta.Estado.PLANIFICADA).order_by('fecha').first()
    )


def inicio_repartidor(request):
    hoy = timezone.localdate()
    ruta = ruta_del_dia()
    siguiente = None
    if ruta:
        ruta.paradas = list(
            ruta.despachos.select_related('pedido__cliente').prefetch_related('pedido__detalles__producto').order_by('orden')
        )
        ruta.total = len(ruta.paradas)
        ruta.entregados = sum(1 for d in ruta.paradas if d.estado == Despacho.Estado.ENTREGADO)
        ruta.faltan = ruta.total - ruta.entregados
        ruta.porcentaje = round(ruta.entregados / ruta.total * 100) if ruta.total else 0
        ruta.completa = ruta.total > 0 and ruta.faltan == 0
        siguiente = next((d for d in ruta.paradas if d.estado != Despacho.Estado.ENTREGADO), None)
    return render(request, 'web/inicio_repartidor.html', {
        'ruta': ruta,
        'siguiente': siguiente,
        'por_asignar': Despacho.objects.filter(ruta__isnull=True).exclude(estado=Despacho.Estado.ENTREGADO).count(),
        'entregados_hoy': Despacho.objects.filter(
            estado=Despacho.Estado.ENTREGADO, fecha_entrega_real__date=hoy
        ).count(),
        'rutas_abiertas': Ruta.objects.exclude(estado=Ruta.Estado.FINALIZADA).count(),
    })


FILTROS_ESTADO = [
    ('activos', 'Activos'),
    ('cotizacion', 'Cotizaciones'),
    ('cocina', 'En cocina'),
    ('listo', 'Listos'),
    ('en_despacho', 'En despacho'),
    ('entregado', 'Entregados'),
    ('cancelado', 'Cancelados'),
]


@rol_requerido('ventas', 'cocina')
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


@rol_requerido('ventas', incluir_admin=False)
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


@rol_requerido('ventas', incluir_admin=False)
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


@rol_requerido('ventas', 'cocina')
def pedido_detalle(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'creado_por').prefetch_related(
            'detalles__producto', 'detalles__personalizaciones__opcion', 'historial__usuario'
        ),
        pk=pk,
    )
    return render(request, 'web/pedido_detalle.html', {
        'pedido': pedido,
        # Todos ven el pedido completo, pero solo Atención y Ventas confirma cotizaciones
        'es_cotizacion': pedido.estado == Pedido.Estado.COTIZACION and 'ventas' in roles_de(request.user),
    })


# ---------------------------------------------------------------
# Vistas del Administrador: cocina, bodega y despachos
# ---------------------------------------------------------------
@rol_requerido('cocina')
def kanban(request):
    """Tablero de cocina. Las tarjetas se cargan y mueven con JavaScript usando la API."""
    columnas = [(estado, Pedido.Estado(estado).label) for estado in Pedido.ESTADOS_KANBAN]
    return render(request, 'web/kanban.html', {
        'columnas': columnas,
        # El Administrador ve el tablero, pero no mueve pedidos (eso es trabajo de Cocina)
        'solo_lectura': rol_principal(request.user) == 'admin',
    })


@rol_requerido('cocina')
def produccion_manana(request):
    """Lo que hay que preparar para mañana: resumen por producto y las comandas."""
    manana = timezone.localdate() + timedelta(days=1)
    pedidos = Pedido.objects.filter(
        fecha_entrega__date=manana, estado__in=Pedido.ESTADOS_KANBAN
    ).select_related('cliente').prefetch_related('detalles__producto').order_by('fecha_entrega')
    resumen = {}
    for pedido in pedidos:
        for detalle in pedido.detalles.all():
            resumen[detalle.producto.nombre] = resumen.get(detalle.producto.nombre, 0) + detalle.cantidad
    return render(request, 'web/produccion_manana.html', {
        'manana': manana,
        'pedidos': pedidos,
        'resumen': sorted(resumen.items(), key=lambda par: (-par[1], par[0])),
        'limite_urgente': timezone.now() + timedelta(hours=3),
    })


FILTROS_MOVIMIENTO = [
    ('todos', 'Todos'),
    ('entrada', 'Entradas'),
    ('ajuste', 'Mermas'),
    ('salida', 'Consumo por pedidos'),
    ('devolucion', 'Devoluciones'),
]
PERIODOS = [('hoy', 'Hoy'), ('semana', 'Últimos 7 días'), ('todo', 'Todo')]


@rol_requerido('bodega')
def movimientos(request):
    """Historial de entradas, mermas, consumos y devoluciones de bodega."""
    tipo = request.GET.get('tipo', 'todos')
    periodo = request.GET.get('periodo', 'semana')
    lista = MovimientoInsumo.objects.select_related('insumo', 'usuario', 'pedido').order_by('-fecha')
    if tipo in MovimientoInsumo.Tipo.values:
        lista = lista.filter(tipo=tipo)
    hoy = timezone.localdate()
    if periodo == 'hoy':
        lista = lista.filter(fecha__date=hoy)
    elif periodo == 'semana':
        lista = lista.filter(fecha__date__gte=hoy - timedelta(days=6))
    pagina = Paginator(lista, 30).get_page(request.GET.get('pagina'))
    return render(request, 'web/movimientos.html', {
        'pagina': pagina,
        'tipo': tipo,
        'periodo': periodo,
        'filtros_tipo': FILTROS_MOVIMIENTO,
        'periodos': PERIODOS,
    })


@rol_requerido('bodega')
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
        # El Administrador ve el inventario y el historial, pero no registra movimientos
        'solo_lectura': rol_principal(request.user) == 'admin',
    })


FILTROS_DIA = [('hoy', 'Hoy'), ('manana', 'Mañana'), ('todas', 'Todas')]


@rol_requerido('repartidor', incluir_admin=False)
def despachos(request):
    """
    Tablero de reparto en tres columnas: Por asignar | Rutas | Entregados hoy.
    Filtro por día: "hoy" incluye también lo atrasado; "manana" solo mañana; "todas" todo.
    """
    hoy = timezone.localdate()
    manana = hoy + timedelta(days=1)
    dia = request.GET.get('dia', 'hoy')
    if dia not in dict(FILTROS_DIA):
        dia = 'hoy'

    sin_ruta = Despacho.objects.filter(ruta__isnull=True).exclude(
        estado=Despacho.Estado.ENTREGADO
    ).select_related('pedido__cliente').order_by('pedido__fecha_entrega')
    rutas = Ruta.objects.exclude(estado=Ruta.Estado.FINALIZADA).prefetch_related(
        'despachos__pedido__cliente'
    ).order_by('fecha', 'nombre')
    rutas_asignables = list(rutas)   # al asignar se puede elegir cualquier ruta abierta

    if dia == 'hoy':
        sin_ruta = sin_ruta.filter(pedido__fecha_entrega__date__lte=hoy)
        rutas = rutas.filter(fecha__lte=hoy)
    elif dia == 'manana':
        sin_ruta = sin_ruta.filter(pedido__fecha_entrega__date=manana)
        rutas = rutas.filter(fecha=manana)

    # Datos de cada hoja de ruta: paradas en orden, avance y cuál es la siguiente.
    rutas = list(rutas)
    for ruta in rutas:
        ruta.paradas = sorted(ruta.despachos.all(), key=lambda d: d.orden)
        ruta.total = len(ruta.paradas)
        ruta.entregados = sum(1 for d in ruta.paradas if d.estado == Despacho.Estado.ENTREGADO)
        ruta.faltan = ruta.total - ruta.entregados
        ruta.porcentaje = round(ruta.entregados / ruta.total * 100) if ruta.total else 0
        ruta.completa = ruta.total > 0 and ruta.faltan == 0
        pendientes = [d for d in ruta.paradas if d.estado != Despacho.Estado.ENTREGADO]
        ruta.siguiente_id = pendientes[0].pk if pendientes else None

    # Paso de la guía que corresponde hacer ahora (1 asignar, 2 iniciar, 3 entregar, 4 finalizar)
    sin_ruta = list(sin_ruta)
    if any(r.estado == Ruta.Estado.EN_CURSO and r.faltan for r in rutas):
        paso = 3
    elif any(r.estado == Ruta.Estado.EN_CURSO and r.completa for r in rutas):
        paso = 4
    elif any(r.estado == Ruta.Estado.PLANIFICADA and r.total for r in rutas):
        paso = 2
    elif sin_ruta:
        paso = 1
    else:
        paso = 0   # todo al día

    return render(request, 'web/despachos.html', {
        'sin_ruta': sin_ruta,
        'rutas': rutas,
        'rutas_asignables': rutas_asignables,
        'entregados_hoy': Despacho.objects.filter(
            estado=Despacho.Estado.ENTREGADO, fecha_entrega_real__date=hoy
        ).select_related('pedido__cliente').order_by('-fecha_entrega_real'),
        'hoy': hoy,
        'dia': dia,
        'filtros_dia': FILTROS_DIA,
        'paso': paso,
        'pasos': [(1, 'Asignar a una ruta'), (2, 'Iniciar ruta'), (3, 'Entregar con firma'), (4, 'Finalizar ruta')],
    })


@rol_requerido('repartidor')
def entregados(request):
    """Historial de entregas realizadas, con quién recibió y la evidencia."""
    periodo = request.GET.get('periodo', 'hoy')
    hoy = timezone.localdate()
    lista = Despacho.objects.filter(estado=Despacho.Estado.ENTREGADO).select_related(
        'pedido__cliente', 'ruta__responsable'
    ).prefetch_related('pedido__detalles__producto').order_by('-fecha_entrega_real')
    if periodo == 'hoy':
        lista = lista.filter(fecha_entrega_real__date=hoy)
    elif periodo == 'semana':
        lista = lista.filter(fecha_entrega_real__date__gte=hoy - timedelta(days=6))
    entregas = list(lista[:100])
    for despacho in entregas:
        # ¿Se entregó a la hora? (se da un margen de 15 minutos)
        despacho.atraso = despacho.fecha_entrega_real > despacho.pedido.fecha_entrega + timedelta(minutes=15)
    return render(request, 'web/entregados.html', {
        'entregas': entregas,
        'periodo': periodo,
        'periodos': PERIODOS,
    })


@rol_requerido('repartidor', incluir_admin=False)
def despacho_entrega(request, pk):
    despacho = get_object_or_404(
        Despacho.objects.select_related('pedido__cliente', 'ruta').prefetch_related(
            'pedido__detalles__producto'
        ),
        pk=pk,
    )
    return render(request, 'web/despacho_entrega.html', {'despacho': despacho})


MAX_INTENTOS_ADMIN = 5


@rol_requerido()
def verificar_admin(request):
    """
    Antes de entrar a Administración se vuelve a pedir la contraseña.
    Tras 5 intentos fallidos se cierra la sesión por seguridad.
    """
    if not es_administrador(request.user):
        raise PermissionDenied
    destino = request.GET.get('next') or request.POST.get('next') or reverse('admin:index')
    if not (destino.startswith(reverse('admin:index'))
            and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()})):
        destino = reverse('admin:index')

    error = ''
    if request.method == 'POST':
        if request.user.check_password(request.POST.get('password', '')):
            request.session[CLAVE_SESION] = time.time() + DURACION_SEGUNDOS
            request.session.pop('intentos_admin', None)
            return redirect(destino)
        intentos = request.session.get('intentos_admin', 0) + 1
        request.session['intentos_admin'] = intentos
        if intentos >= MAX_INTENTOS_ADMIN:
            logout(request)
            messages.error(request, 'Se cerró la sesión por demasiados intentos fallidos. Vuelve a ingresar.')
            return redirect('login')
        error = f'Contraseña incorrecta. Te quedan {MAX_INTENTOS_ADMIN - intentos} intento(s).'
    return render(request, 'web/verificar_admin.html', {'destino': destino, 'error': error})
