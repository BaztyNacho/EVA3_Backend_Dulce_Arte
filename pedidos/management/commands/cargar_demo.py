"""
Carga datos de demostración para presentar Dulce Arte: clientes, pedidos en todas
las etapas, rutas de despacho, entregas con firma o comprobante y movimientos de bodega.

Uso:
    python manage.py cargar_catalogo   (primero: productos, insumos y extras)
    python manage.py crear_roles
    python manage.py cargar_demo

Todo se crea con las MISMAS reglas de negocio del sistema (services.py): al confirmar
se descuenta stock, el Kanban avanza etapa por etapa, las entregas exigen firma o
comprobante y cada cambio queda en el historial. Si falta stock para un pedido, primero
se registra una "Entrada" en bodega (como haría el encargado de bodega).

Solo se ejecuta una vez: si ya hay datos de demostración, no hace nada.
"""

import io
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from despachos.models import Despacho, Ruta
from despachos.services import confirmar_entrega
from inventario.models import Insumo, MovimientoInsumo, Producto
from inventario.services import registrar_movimiento
from pedidos.management.commands.crear_roles import BODEGA, COCINA, REPARTIDOR
from pedidos.models import Cliente, DetallePedido, HistorialEstado, Pedido, PersonalizacionDetalle
from pedidos.services import (
    avanzar_estado,
    calcular_requerimientos,
    cancelar_pedido,
    confirmar_cotizacion,
    rechazar_control_calidad,
)

DOMINIO_DEMO = 'demo.dulcearte.cl'   # así se reconocen los clientes de demostración

CLIENTES = [
    ('María José Fuentes', '+56 9 8765 4321', 'Los Aromos 1234, Ñuñoa'),
    ('Pedro Soto Rivas', '+56 9 7123 4567', 'Av. Grecia 890, Peñalolén'),
    ('Camila Rojas Pérez', '+56 9 6234 5678', 'Irarrázaval 3050, Ñuñoa'),
    ('Javier Muñoz Díaz', '+56 9 5345 6789', 'Av. Los Leones 1520, Providencia'),
    ('Fernanda Contreras', '+56 9 9456 7890', 'Pocuro 2244, Providencia'),
    ('Ignacio Vargas Silva', '+56 9 8567 8901', 'Av. Tobalaba 4400, La Reina'),
    ('Valentina Herrera', '+56 9 7678 9012', 'Simón Bolívar 5870, La Reina'),
    ('Sebastián Morales', '+56 9 6789 0123', 'Av. Macul 3100, Macul'),
    ('Catalina Núñez Castro', '+56 9 5890 1234', 'Quilín 2950, Macul'),
    ('Diego Espinoza Lagos', '+56 9 9901 2345', 'Av. Apoquindo 6300, Las Condes'),
    ('Antonia Reyes Pino', '+56 9 8012 3456', 'Manquehue Sur 520, Las Condes'),
    ('Matías Gutiérrez', '+56 9 7134 5678', 'Av. Vicuña Mackenna 7255, La Florida'),
]

DISENOS = [
    'Escribir "Feliz cumpleaños, Sofía" en letra cursiva dorada.',
    'Decoración con flores de buttercream rosado y hojas verdes.',
    'Temática de unicornio: tonos pastel y cuerno dorado.',
    'Sin decoración extra, solo frutas frescas encima.',
    'Escribir "Felices 60, papá" y velas números 6 y 0.',
    'Colores azul y blanco, con chispas plateadas.',
    'Mensaje "Feliz aniversario" con corazones de chocolate.',
    '',
    '',
]

COMENTARIOS = ['', '', '', 'Sin nueces, por favor.', 'Que el bizcocho quede bien húmedo.', 'Cortar en 12 porciones.']

RECEPTORES = ['Carmen (mamá)', 'Conserje del edificio', 'Luis (hermano)', 'La misma clienta', 'El mismo cliente', 'Rosa (vecina)']


class Command(BaseCommand):
    help = 'Carga clientes, pedidos en todas las etapas, rutas y entregas de demostración.'

    def handle(self, *args, **options):
        if Cliente.objects.filter(email__endswith=DOMINIO_DEMO).exists():
            self.stdout.write(self.style.WARNING('Los datos de demostración ya estaban cargados. No se hizo nada.'))
            return
        if Producto.objects.filter(activo=True).count() < 5:
            raise CommandError('Primero ejecuta "python manage.py cargar_catalogo".')

        self.azar = random.Random(2026)          # semilla fija: siempre los mismos datos
        self.ahora = timezone.localtime()
        self.admin = User.objects.filter(is_superuser=True).order_by('pk').first()
        if not self.admin:
            raise CommandError('Crea primero un superusuario con "python manage.py createsuperuser".')
        # Si existen usuarios de cada rol, las acciones quedan registradas a su nombre
        self.cocina = self._usuario_de(COCINA)
        self.bodega = self._usuario_de(BODEGA)
        self.repartidor = self._usuario_de(REPARTIDOR)
        self.ventas = User.objects.filter(groups__name='Atención y Ventas').first() or self.admin
        self.productos = list(Producto.objects.filter(activo=True).prefetch_related('opciones'))

        with transaction.atomic():
            self.clientes = self._crear_clientes()
            resumen = self._crear_pedidos()
            self._movimientos_de_bodega()

        self.stdout.write(self.style.SUCCESS(f'Clientes: {len(self.clientes)}.'))
        for texto in resumen:
            self.stdout.write(self.style.SUCCESS(texto))
        self.stdout.write(self.style.SUCCESS('Datos de demostración cargados.'))

    # ------------------------------------------------------------------
    # Ayudantes
    # ------------------------------------------------------------------
    def _usuario_de(self, grupo):
        return User.objects.filter(groups__name=grupo).order_by('pk').first() or self.admin

    def _crear_clientes(self):
        clientes = []
        for nombre, telefono, direccion in CLIENTES:
            usuario_correo = nombre.split()[0].lower().replace('í', 'i').replace('é', 'e').replace('á', 'a')
            clientes.append(Cliente.objects.create(
                nombre=nombre, telefono=telefono, direccion=direccion,
                email=f'{usuario_correo}{len(clientes) + 1}@{DOMINIO_DEMO}',
            ))
        return clientes

    def _nuevo_pedido(self, tipo='retiro', productos=1):
        """Crea una cotización con 1 a 3 productos, algunos con extras y comentario."""
        cliente = self.azar.choice(self.clientes)
        pedido = Pedido.objects.create(
            cliente=cliente,
            fecha_entrega=self.ahora + timedelta(days=3),      # válida (24 h); luego se ajusta
            tipo_entrega=tipo,
            direccion_entrega=cliente.direccion if tipo == 'despacho' else '',
            diseno=self.azar.choice(DISENOS),
            creado_por=self.ventas,
        )
        for producto in self.azar.sample(self.productos, productos):
            detalle = DetallePedido.objects.create(
                pedido=pedido, producto=producto,
                cantidad=self.azar.choice([1, 1, 1, 2]),
                comentario=self.azar.choice(COMENTARIOS),
            )
            opciones = list(producto.opciones.filter(activo=True))
            if opciones and self.azar.random() < 0.45:
                PersonalizacionDetalle.objects.create(
                    detalle=detalle, opcion=self.azar.choice(opciones),
                    porciones=self.azar.choice([1, 1, 2, -1]),
                )
        pedido.calcular_total()
        return pedido

    def _asegurar_stock(self, pedido):
        """Si falta algún insumo, bodega registra una compra antes de confirmar."""
        for insumo_id, necesario in calcular_requerimientos(pedido).items():
            insumo = Insumo.objects.get(pk=insumo_id)
            if insumo.stock_actual < necesario:
                compra = (necesario - insumo.stock_actual + insumo.stock_minimo * 2).quantize(Decimal('0.001'))
                registrar_movimiento(insumo, MovimientoInsumo.Tipo.ENTRADA, compra, self.bodega,
                                     motivo='Compra a proveedor')

    def _confirmar(self, pedido):
        self._asegurar_stock(pedido)
        confirmar_cotizacion(pedido, self.ventas)

    def _avanzar(self, pedido, veces):
        for _ in range(veces):
            avanzar_estado(pedido, self.cocina)

    def _fechar(self, pedido, entrega, creado):
        """Ajusta las fechas para que el pedido parezca hecho en otro momento."""
        Pedido.objects.filter(pk=pedido.pk).update(fecha_entrega=entrega, creado_en=creado)
        cambios = list(HistorialEstado.objects.filter(pedido=pedido).order_by('pk'))
        if cambios:
            fin = min(entrega, self.ahora)
            paso = max((fin - creado) / (len(cambios) + 1), timedelta(minutes=5))
            for i, cambio in enumerate(cambios, start=1):
                HistorialEstado.objects.filter(pk=cambio.pk).update(fecha=creado + paso * i)
        MovimientoInsumo.objects.filter(pedido=pedido).update(fecha=creado + timedelta(minutes=10))

    def _hora(self, dias, hora, minuto=0):
        base = (self.ahora + timedelta(days=dias)).replace(hour=hora, minute=minuto, second=0, microsecond=0)
        return base

    def _firma(self):
        """Dibuja una firma de ejemplo (PNG con fondo transparente)."""
        imagen = Image.new('RGBA', (360, 140), (255, 255, 255, 0))
        dibujo = ImageDraw.Draw(imagen)
        x, y = 20, 90
        puntos = []
        for i in range(40):
            x += self.azar.randint(5, 9)
            y = max(25, min(120, y + self.azar.randint(-18, 18)))
            puntos.append((x, y))
        dibujo.line([(20, 90)] + puntos, fill=(40, 25, 20, 255), width=4, joint='curve')
        salida = io.BytesIO()
        imagen.save(salida, 'PNG')
        return ContentFile(salida.getvalue(), name='firma_demo.png')

    def _comprobante(self, pedido):
        """Imagen de una guía de despacho firmada (simula la foto del comprobante)."""
        imagen = Image.new('RGB', (420, 560), (250, 247, 240))
        dibujo = ImageDraw.Draw(imagen)
        dibujo.rectangle([20, 20, 400, 540], outline=(120, 100, 90), width=3)
        dibujo.text((40, 40), 'DULCE ARTE - Guía de despacho', fill=(60, 36, 32))
        dibujo.text((40, 80), f'Pedido #{pedido.pk}', fill=(60, 36, 32))
        dibujo.text((40, 110), pedido.cliente.nombre, fill=(60, 36, 32))
        for i in range(8):
            dibujo.line([(40, 160 + i * 34), (380, 160 + i * 34)], fill=(200, 190, 180), width=1)
        dibujo.text((40, 460), 'Recibí conforme:', fill=(60, 36, 32))
        dibujo.line([(40, 510), (360, 495)], fill=(30, 30, 90), width=3)
        salida = io.BytesIO()
        imagen.save(salida, 'JPEG', quality=80)
        return ContentFile(salida.getvalue(), name='comprobante_demo.jpg')

    # ------------------------------------------------------------------
    # Pedidos en todas las etapas
    # ------------------------------------------------------------------
    def _crear_pedidos(self):
        conteo = {}

        def contar(etiqueta):
            conteo[etiqueta] = conteo.get(etiqueta, 0) + 1

        # 1. Cotizaciones pendientes (para los próximos días)
        for dias in [2, 3, 4, 6]:
            p = self._nuevo_pedido(self.azar.choice(['retiro', 'despacho']), self.azar.randint(1, 2))
            self._fechar(p, self._hora(dias, self.azar.choice([11, 15, 17])), self.ahora - timedelta(hours=self.azar.randint(1, 20)))
            contar('Cotizaciones')

        # 2. En cocina: (avances, horas hasta la entrega, tipo)
        en_cocina = [
            (0, 2, 'retiro'), (0, 26, 'retiro'), (0, 30, 'despacho'),              # Recibido (uno urgente)
            (1, 3, 'despacho'), (1, 20, 'retiro'), (1, 28, 'retiro'),              # En preparación
            (2, 5, 'retiro'), (2, 22, 'despacho'), (2, 27, 'retiro'),              # Horneado/Decorado
            (3, 6, 'retiro'), (3, 24, 'despacho'),                                  # Control de calidad
            (4, 2, 'retiro'), (4, 4, 'despacho'), (4, 7, 'despacho'),              # Listo
        ]
        for avances, horas, tipo in en_cocina:
            p = self._nuevo_pedido(tipo, self.azar.randint(1, 3))
            self._confirmar(p)
            self._avanzar(p, avances)
            if avances == 3 and horas == 6:
                # Un rechazo en control de calidad que se corrigió y volvió a revisión
                rechazar_control_calidad(p, self.cocina, 'Decoración dispareja, volver a cubrir')
                self._avanzar(p, 2)
            self._fechar(p, self.ahora + timedelta(hours=horas), self.ahora - timedelta(days=1, hours=self.azar.randint(1, 10)))
            contar(Pedido.Estado(Pedido.objects.get(pk=p.pk).estado).label)

        # 3. Entregados en tienda (días anteriores)
        for dias in [1, 2, 3, 5]:
            p = self._nuevo_pedido('retiro', self.azar.randint(1, 2))
            self._confirmar(p)
            self._avanzar(p, 5)                       # Listo -> Entregado en tienda
            entrega = self._hora(-dias, self.azar.choice([12, 16, 18]))
            self._fechar(p, entrega, entrega - timedelta(days=2))
            contar('Entregados en tienda')

        # 4. Despachos entregados en rutas anteriores (finalizadas)
        for dias, cantidad in [(1, 3), (3, 2)]:
            ruta = Ruta.objects.create(
                nombre=f'Ruta oriente {self._hora(-dias, 9):%d-%m}', fecha=self._hora(-dias, 9).date(),
                responsable=self.repartidor, estado=Ruta.Estado.EN_CURSO,
            )
            for orden in range(1, cantidad + 1):
                p = self._nuevo_pedido('despacho', self.azar.randint(1, 2))
                self._confirmar(p)
                self._avanzar(p, 5)                   # Listo -> En despacho (crea el despacho)
                despacho = Despacho.objects.get(pedido=p)
                despacho.ruta, despacho.orden, despacho.estado = ruta, orden, Despacho.Estado.EN_CAMINO
                despacho.save()
                con_foto = orden % 2 == 0
                confirmar_entrega(
                    despacho, self.repartidor, self.azar.choice(RECEPTORES),
                    firma=None if con_foto else self._firma(),
                    comprobante=self._comprobante(p) if con_foto else None,
                    observaciones=self.azar.choice(['', '', 'Se dejó en conserjería.', 'Cliente pidió tocar el timbre dos veces.']),
                )
                programada = self._hora(-dias, 11 + orden * 2)
                real = programada + timedelta(minutes=self.azar.choice([-10, 5, 12, 40]))  # alguno con atraso
                self._fechar(p, programada, programada - timedelta(days=2))
                Despacho.objects.filter(pk=despacho.pk).update(fecha_entrega_real=real)
                contar('Despachos entregados')
            Ruta.objects.filter(pk=ruta.pk).update(estado=Ruta.Estado.FINALIZADA)

        # 5. Ruta de hoy en curso: una parada entregada y dos pendientes
        ruta_hoy = Ruta.objects.create(
            nombre='Ruta centro, tarde', fecha=self.ahora.date(),
            responsable=self.repartidor, estado=Ruta.Estado.EN_CURSO,
        )
        for orden in range(1, 4):
            p = self._nuevo_pedido('despacho', self.azar.randint(1, 2))
            self._confirmar(p)
            self._avanzar(p, 5)
            despacho = Despacho.objects.get(pedido=p)
            despacho.ruta, despacho.orden, despacho.estado = ruta_hoy, orden, Despacho.Estado.EN_CAMINO
            despacho.save()
            self._fechar(p, self.ahora + timedelta(hours=orden), self.ahora - timedelta(days=2))
            if orden == 1:
                confirmar_entrega(despacho, self.repartidor, 'La misma clienta', firma=self._firma())
                Despacho.objects.filter(pk=despacho.pk).update(fecha_entrega_real=self.ahora - timedelta(minutes=40))
                contar('Despachos entregados')
            else:
                contar('En despacho (ruta de hoy)')

        # 6. Por asignar: uno nuevo y un intento fallido para reintentar
        for fallido in [False, True]:
            p = self._nuevo_pedido('despacho', 1)
            self._confirmar(p)
            self._avanzar(p, 5)
            self._fechar(p, self.ahora + timedelta(hours=5 if not fallido else 1), self.ahora - timedelta(days=2))
            if fallido:
                Despacho.objects.filter(pedido=p).update(
                    estado=Despacho.Estado.FALLIDO, observaciones='No había nadie en el domicilio',
                )
            contar('Por asignar a ruta')

        # 7. Cancelados: una cotización y un pedido recibido (sus insumos vuelven a bodega)
        p = self._nuevo_pedido('retiro', 1)
        cancelar_pedido(p, self.admin, 'El cliente ya no lo necesita')
        self._fechar(p, self._hora(2, 12), self.ahora - timedelta(days=1))
        p = self._nuevo_pedido('despacho', 2)
        self._confirmar(p)
        cancelar_pedido(p, self.admin, 'Cliente cambió la fecha del evento; se hará otro pedido')
        self._fechar(p, self._hora(3, 15), self.ahora - timedelta(days=1))
        conteo['Cancelados'] = 2

        return [f'{nombre}: {cantidad}.' for nombre, cantidad in conteo.items()]

    # ------------------------------------------------------------------
    # Bodega: compras y mermas de los últimos días
    # ------------------------------------------------------------------
    def _movimientos_de_bodega(self):
        compras = [('Harina sin polvos de hornear', '10', 3), ('Huevos', '60', 2), ('Mantequilla sin sal', '4', 1)]
        mermas = [('Frutillas', '0.4', 'Frutillas en mal estado'), ('Crema para batir', '0.5', 'Producto vencido'),
                  ('Huevos', '6', 'Se quebraron al recibirlos')]
        for nombre, cantidad, dias in compras:
            insumo = Insumo.objects.filter(nombre=nombre).first()
            if insumo:
                mov = registrar_movimiento(insumo, MovimientoInsumo.Tipo.ENTRADA, Decimal(cantidad), self.bodega,
                                           motivo='Compra semanal a proveedor')
                MovimientoInsumo.objects.filter(pk=mov.pk).update(fecha=self._hora(-dias, 9, 30))
        for nombre, cantidad, motivo in mermas:
            insumo = Insumo.objects.filter(nombre=nombre).first()
            if insumo and insumo.stock_actual >= Decimal(cantidad):
                mov = registrar_movimiento(insumo, MovimientoInsumo.Tipo.AJUSTE, Decimal(cantidad), self.bodega, motivo=motivo)
                MovimientoInsumo.objects.filter(pk=mov.pk).update(fecha=self.ahora - timedelta(hours=self.azar.randint(2, 30)))
