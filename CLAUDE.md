# Dulce Arte — Contexto del proyecto para Claude Code

## Qué es
Sistema de Trazabilidad y Pedidos para una Pastelería Artesanal (Evaluación Parcial N°3, Desarrollo Backend, INACAP).
Proyecto individual. Desplegado en AWS EC2: http://54.84.222.180/

El backend está **terminado y probado** (49 pruebas de API). La fase actual es de **ajustes visuales e interacción**.

## Stack
- Python 3.14, Django 5.2 LTS, Django REST Framework, drf-spectacular, PostgreSQL.
- Frontend: templates de Django + CSS + JavaScript sin frameworks (fetch a la API con la sesión de Django y token CSRF).
- Producción: Nginx + Gunicorn en EC2 (`deploy/`).

## Entorno local (Windows 11)
- Entorno virtual FUERA del proyecto: `C:\Users\bazty\venvs\dulce-arte`
- Activar: `& "$env:USERPROFILE\venvs\dulce-arte\Scripts\Activate.ps1"`
- Servidor: `python manage.py runserver` → http://127.0.0.1:8000/
- No crear entornos virtuales dentro del proyecto (la carpeta está en OneDrive).
- Usuarios locales: `admin_dulce` (Administrador) y `vendedora1` (Atención y Ventas). Pide las contraseñas al usuario cuando las necesites; nunca las escribas en archivos.

## Estructura
| App | Contenido |
|---|---|
| `inventario` | Insumo (con imagen), Producto (con tiempo_preparacion en minutos), RecetaItem (BOM), OpcionPersonalizacion (extras por producto), MovimientoInsumo |
| `pedidos` | Cliente, Pedido, DetallePedido, PersonalizacionDetalle, HistorialEstado. Reglas de negocio en `pedidos/services.py` |
| `despachos` | Ruta, Despacho (firma/comprobante). Reglas en `despachos/services.py` |
| `web` | Interfaz web: `web/views.py`, `web/templates/web/`, `web/static/web/` |
| `config` | settings, urls, rutas de la API (`config/api.py`) |

### Interfaz web (app `web`)
| Ruta | Template | JS | Rol |
|---|---|---|---|
| `/ingresar/` | `login.html` | — | todos |
| `/` | `inicio.html` | — | ambos |
| `/catalogo/` | `catalogo.html` | — | solo Atención y Ventas |
| `/pedidos/` | `pedidos_lista.html` | — | ambos |
| `/pedidos/nuevo/` | `pedido_nuevo.html` | `cotizador.js` | ambos |
| `/pedidos/<id>/` | `pedido_detalle.html` | `pedido_detalle.js` | ambos |
| `/cocina/` | `kanban.html` | `kanban.js` (+ SortableJS en `vendor/`) | Administrador |
| `/bodega/` | `bodega.html` | `bodega.js` | Administrador |
| `/despachos/` | `despachos.html` | `despachos.js` | Administrador |
| `/despachos/<id>/entregar/` | `despacho_entrega.html` | `firma.js` | Administrador |
| `/admin/` | Django Admin con `templates/admin/base_site.html` | — | Administrador |

- `web/static/web/js/api.js`: `llamarApi()`, `textosDeError()`, `mostrarAviso()`, `clp()`. Úsalos en todo JS nuevo.
- `web/templates/web/_comanda.html`: tarjeta "comanda" reutilizable.
- `web/templates/web/_imagen.html`: imagen con reemplazo elegante (inicial sobre color) si no hay foto. Uso: `{% include 'web/_imagen.html' with imagen=obj.imagen nombre=obj.nombre clase='...' %}`.
- Filtros de template en `web/templatetags/dulce.py`: `clp`, `porcentaje`, `inicial`, `tono`.

### Endpoints de la API que usa el frontend
- `GET /api/pedidos/kanban/` · `POST /api/pedidos/<id>/avanzar/` · `POST /api/pedidos/<id>/rechazar-calidad/` (`{motivo}`)
- `POST /api/movimientos-insumo/` (`{insumo, tipo: 'entrada'|'ajuste', cantidad, motivo}`) — `ajuste` = merma (resta stock).
- `POST /api/pedidos/` · `POST /api/pedidos/<id>/confirmar/` · `GET /api/pedidos/<id>/disponibilidad/`
- `PATCH /api/despachos/<id>/` · `POST /api/despachos/<id>/confirmar-entrega/` · `POST /api/rutas/`
- Documentación completa: http://127.0.0.1:8000/api/docs/

## Identidad visual (sistema de diseño en `web/static/web/css/dulce.css`)
- Variables en `:root`: `--vainilla` (fondo), `--papel`, `--chocolate` (texto), `--frambuesa` (principal), `--caramelo` (detalles), `--pistacho` (éxito), `--alerta`.
- Tipografía: **Fraunces** (títulos) + **Work Sans** (texto), desde Google Fonts.
- Elemento distintivo: la **comanda** (ticket de pedido con borde superior perforado).
- Usa siempre las variables existentes; no inventes colores nuevos sin necesidad.

## Reglas de trabajo (IMPORTANTE)
1. **No modificar el backend** sin preguntar: modelos, migraciones, `services.py`, serializers, `api.py`, `admin.py` y permisos. Las reglas de negocio viven en el servidor y ya están probadas.
2. Los cambios visuales van en `web/templates/`, `web/static/web/` y `templates/admin/`.
3. **Django Admin:** solo cambios visuales (CSS y templates en `templates/admin/`). No cambiar `admin.py` ni quitar funcionalidades del Admin.
4. **Accesibilidad:** foco visible, navegación con teclado, `aria-*` en ventanas modales (`role="dialog"`, foco atrapado, Escape para cerrar), contraste suficiente.
5. **Animaciones** con propósito, cortas (menos de 300 ms), con `cubic-bezier` personalizadas y siempre respetando `prefers-reduced-motion`.
6. Responsivo: debe funcionar en celular (la entrega con firma se usa en el teléfono).
7. Explicar cada cambio de forma simple: el estudiante debe poder defenderlo.
8. Entregar archivos completos al modificar código.
9. Nombres de variables, clases y textos en español.
10. Nunca subir `.env` ni escribir claves en el código.
11. Al terminar cada tarea, probar la página con Playwright CLI y resumir qué se hizo (para `prompts_ia.md`).
