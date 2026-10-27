# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Atención y Ventas (vendedores):** trabajan en el mostrador de la pastelería, frente al cliente. Muestran el catálogo, cotizan pedidos personalizados, los registran y confirman, y consultan su estado.
- **Administrador:** coordina la cocina (tablero Kanban), la bodega de insumos y el reparto. Confirma entregas con firma digital o foto del comprobante desde el celular.

## Product Purpose

Sistema interno de trazabilidad y pedidos para Dulce Arte, una pastelería artesanal chilena. Conecta tres áreas que antes no se coordinaban: la toma de pedidos personalizados, la disponibilidad de insumos en bodega y los tiempos de cocina. El éxito es que cada pedido confirmado descuente sus insumos según la receta, avance por la cocina sin saltarse etapas y termine con una entrega confirmada y registrada.

## Positioning

Cada pedido personalizado queda ligado a su receta (lista de materiales) y a su historial: al confirmarlo se verifica y descuenta el stock real, y cada cambio de etapa o movimiento de bodega queda registrado con usuario, fecha y motivo.

## Operating Context

- Mostrador: el vendedor usa el catálogo y el cotizador frente al cliente; la información debe leerse de un vistazo.
- Cocina: tablero Kanban con etapas Recibido → En Preparación → Horneado/Decorado → Control de Calidad → Listo. Se arrastra y suelta (también en pantallas táctiles) o se usan botones. Control de Calidad puede rechazar con motivo.
- Bodega: entradas de stock, mermas y alertas de stock bajo.
- Reparto: rutas con paradas ordenadas; la entrega con firma se hace en el teléfono.
- Django Admin (`/admin/`) para la gestión completa por el Administrador.

## Capabilities and Constraints

- Django 5.2 + Django REST Framework + PostgreSQL; frontend con templates de Django, CSS y JavaScript sin frameworks (fetch a la API con sesión y CSRF). SortableJS para el Kanban. Desplegado en AWS EC2 con Nginx + Gunicorn.
- El backend está terminado y probado; la fase actual es solo de ajustes visuales e interacción. Modelos, servicios, serializers, API, `admin.py` y permisos no se cambian sin preguntar.
- Roles: Atención y Ventas no accede a cocina, bodega, despachos ni Admin.
- Reglas de negocio en el servidor: entrega con mínimo 24 horas de anticipación, extras de −5 a +5 porciones, no se saltan etapas, merma no puede superar el stock.
- Textos, nombres de clases y variables en español (Chile). Moneda en pesos chilenos (CLP).
- Proyecto académico individual (Evaluación Parcial N°3, Desarrollo Backend, INACAP): cada cambio debe poder explicarse y defenderse.

## Brand Commitments

- Nombre: Dulce Arte.
- Tono confirmado: cálido, artesanal y profesional; elegante pero fácil de usar.
- La identidad visual actual (paleta vainilla, frambuesa, chocolate y caramelo; Fraunces + Work Sans; la "comanda", un ticket con borde perforado) es el punto de partida, pero el usuario confirmó que **no es obligatoria** y puede cambiarse si una propuesta lo justifica.

## Evidence on Hand

- Productos e insumos pueden tener imagen; cuando no hay foto se usa un reemplazo con la inicial sobre color (`web/templates/web/_imagen.html`). Hoy casi no hay fotos reales cargadas.
- No hay testimonios, clientes, cifras ni fotografías de la pastelería: no inventarlos.

## Product Principles

1. Rapidez en el mostrador: el vendedor atiende al cliente mientras usa el sistema; nada debe obligarlo a buscar.
2. Evitar errores costosos: las acciones que mueven pedidos o stock se confirman y explican su efecto.
3. Trazabilidad visible: el estado y el historial de cada pedido deben entenderse sin preguntar.
4. Funciona donde se trabaja: escritorio en el mostrador, celular en el reparto.

## Accessibility & Inclusion

- Foco visible y navegación completa con teclado.
- Ventanas modales con `role="dialog"`, `aria-modal`, foco atrapado y cierre con Escape.
- Contraste suficiente y animaciones cortas que respetan `prefers-reduced-motion`.
- Uso táctil en celular (entrega con firma, Kanban).
