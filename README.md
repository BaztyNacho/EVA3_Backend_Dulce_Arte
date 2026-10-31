# Dulce Arte — Sistema de Trazabilidad y Pedidos para Pastelería Artesanal

Evaluación Parcial N°3 · Desarrollo Backend · INACAP
Autor: Bastian Sandoval

## Aplicación desplegada en AWS

| | |
|---|---|
| **Dirección de la aplicación** | **https://dulcearte.duckdns.org/** |
| IP pública (AWS EC2, Elastic IP) | 54.84.222.180 (redirige al dominio con HTTPS) |
| Panel de administración | https://dulcearte.duckdns.org/admin/ |
| Documentación de la API (Swagger) | https://dulcearte.duckdns.org/api/docs/ (requiere iniciar sesión) |
| API navegable | https://dulcearte.duckdns.org/api/ |

Las credenciales de los usuarios de prueba (Administrador y Atención y Ventas) se entregan al docente en la defensa; no se publican en el repositorio.

---

## El problema

Dulce Arte no tenía coordinación entre la toma de pedidos personalizados, la disponibilidad de insumos en bodega y los tiempos de cocina. Este sistema conecta esas tres áreas: cada pedido confirmado descuenta automáticamente sus insumos según la receta, avanza por un tablero de cocina y termina con una entrega confirmada con firma o comprobante.

## Funcionalidades (requerimientos del caso)

1. **Cotización y registro de pedidos personalizados**
   - Cliente existente o nuevo, fecha y hora de entrega (mínimo 24 horas de anticipación), retiro o despacho.
   - Productos con cantidad, extras por producto (de −5 a +5 porciones) y comentario libre.
   - Descripción del diseño e imagen de referencia. Total calculado automáticamente.
2. **Tablero Kanban de cocina:** Recibido → En Preparación → Horneado/Decorado → Control de Calidad → Listo.
   - Arrastrar y soltar (también en pantallas táctiles) o botones. No se pueden saltar etapas.
   - Rechazo en Control de Calidad con motivo (vuelve a En Preparación).
3. **Inventario con Lista de Materiales (BOM)**
   - Cada producto tiene su receta. Al confirmar una cotización se verifica el stock y se descuentan los insumos (receta + extras).
   - Alertas de stock bajo, movimientos de bodega (entradas, mermas) y devolución de insumos al cancelar.
4. **Rutas de despacho**
   - Rutas con paradas ordenadas. Entrega confirmada con **firma digital en pantalla** y/o **foto del comprobante**.
   - Registro de intentos fallidos.

**Trazabilidad:** cada cambio de estado queda en un historial con usuario, fecha y motivo, y cada entrada o salida de bodega queda registrada como movimiento.

## Roles y seguridad

| Rol | Acceso |
|---|---|
| **Administrador** | Supervisa: ve pedidos (y los busca), el tablero de cocina, el inventario con su historial y el historial completo de despachos, **sin intervenir** en el trabajo de los demás roles. Gestiona todo desde el Django Admin, que pide confirmar la contraseña antes de entrar. |
| **Atención y Ventas** | Catálogo para atender clientes, cotizar, registrar y confirmar pedidos, consultar su estado. |
| **Cocina** | Tablero Kanban, detalle de pedidos (con precios) y producción de mañana. No cotiza ni cancela. |
| **Bodega** | Inventario, registro de entradas y mermas, historial de movimientos. No crea ni edita insumos o recetas. |
| **Repartidor** | Su ruta del día, rutas de despacho, entrega con firma o foto e historial de entregas. |

Cada rol tiene su propia pantalla de inicio y solo ve en la barra lo que corresponde a su puesto. Las restricciones se aplican en las vistas web **y** en la API (no basta con ocultar enlaces).

- Autenticación con sesiones de Django; la API usa la misma sesión con protección CSRF.
- Antes de entrar al Django Admin se vuelve a pedir la contraseña (middleware `web/middleware.py`); la verificación dura 10 minutos y tras 5 intentos fallidos se cierra la sesión.
- Permisos por grupo (`DjangoModelPermissions`) y reglas por rol en la API y en las vistas.
- Reglas de negocio validadas en el servidor (capa `services.py` con transacciones atómicas), no solo en el navegador.
- Configuración sensible en variables de entorno (`.env`); `DEBUG=False` en producción.
- HTTPS con certificado de Let's Encrypt; las cookies de sesión y CSRF solo viajan cifradas.
- PostgreSQL solo acepta conexiones locales (no está expuesto a internet).

## Tecnologías

- **Backend:** Python 3.14, Django 5.2 LTS, Django REST Framework, drf-spectacular (Swagger)
- **Base de datos:** PostgreSQL
- **Frontend:** templates de Django + HTML/CSS/JavaScript (fetch a la API), SortableJS
- **Servidor:** AWS EC2 (Ubuntu), Nginx + Gunicorn, dominio DuckDNS y certificado Let's Encrypt

## Arquitectura

```
Navegador ──► Nginx (443 HTTPS; el 80 redirige) ──► Gunicorn ──► Django + DRF ──► PostgreSQL
                 │                                              (misma instancia EC2)
                 └── sirve /static/ y /media/ directamente
```

| App | Contenido |
|---|---|
| `inventario` | Insumos, productos, recetas (BOM), extras, movimientos de bodega |
| `pedidos` | Clientes, pedidos, detalles, personalizaciones, historial; reglas de negocio en `services.py` |
| `despachos` | Rutas y despachos con firma/comprobante |
| `web` | Interfaz web (login, cotizador, Kanban, bodega, despachos) |
| `config` | Configuración del proyecto y rutas de la API |

## Rutas principales

| Ruta | Descripción |
|---|---|
| `/ingresar/` | Inicio de sesión |
| `/` | Inicio con resumen del día |
| `/catalogo/` | Catálogo de productos con ingredientes, extras, precio y tiempo de preparación (Atención y Ventas) |
| `/cocina/manana/` | Producción de mañana (Cocina) |
| `/bodega/movimientos/` | Historial de movimientos de bodega (Bodega) |
| `/despachos/entregados/` | Historial de entregas con firma o comprobante (Repartidor) |
| `/pedidos/` · `/pedidos/nuevo/` | Lista de pedidos y cotizador |
| `/cocina/` | Tablero Kanban (Administrador) |
| `/bodega/` | Stock y movimientos (Administrador) |
| `/despachos/` | Rutas y entregas (Administrador) |
| `/admin/` | Django Admin personalizado |
| `/api/` · `/api/docs/` | API REST y su documentación |

---

## Ejecución local (Windows)

Requisitos: Python 3.12 o superior, PostgreSQL y Git.

```powershell
# 1. Clonar el repositorio
git clone https://github.com/BaztyNacho/EVA3_Backend_Dulce_Arte.git
cd EVA3_Backend_Dulce_Arte

# 2. Entorno virtual e instalación de dependencias
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Crear la base de datos en PostgreSQL (con `psql -U postgres`):

```sql
CREATE USER dulce_user WITH PASSWORD 'tu_contraseña';
CREATE DATABASE db_dulce_arte OWNER dulce_user;
```

4. Copiar `.env.example` como `.env` y completar los valores (`SECRET_KEY`, contraseña de la base de datos).

```powershell
# 5. Preparar la base de datos y los datos iniciales
python manage.py migrate
python manage.py crear_roles        # grupos Administrador, Atención y Ventas, Cocina, Bodega y Repartidor
python manage.py cargar_catalogo    # 30 insumos, 11 productos con receta, 18 extras y fotos
python manage.py createsuperuser
python manage.py cargar_demo        # (opcional) clientes, pedidos en todas las etapas, rutas y entregas de ejemplo

# 6. Ejecutar
python manage.py runserver
```

Abrir http://127.0.0.1:8000/. Los usuarios de cada rol se crean en el Admin y se agregan a su grupo (por ejemplo, "Cocina").

## Despliegue en AWS EC2

Instancia Ubuntu en AWS Academy (us-east-1) con Elastic IP, grupo de seguridad con puertos 22 (SSH), 80 (HTTP) y 443 (HTTPS).

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip postgresql nginx git

# Base de datos
sudo -u postgres psql -c "CREATE USER dulce_user WITH PASSWORD '...';"
sudo -u postgres psql -c "CREATE DATABASE db_dulce_arte OWNER dulce_user;"

# Proyecto
cd ~
git clone https://github.com/BaztyNacho/EVA3_Backend_Dulce_Arte.git dulce-arte
cd dulce-arte
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
nano .env   # DEBUG=False, SECRET_KEY nueva, ALLOWED_HOSTS=<IP>, CSRF_TRUSTED_ORIGINS=http://<IP>, datos de la BD

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py crear_roles
python manage.py cargar_catalogo
python manage.py createsuperuser

# Gunicorn como servicio
sudo cp deploy/gunicorn.service /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn

# Nginx
sudo cp deploy/nginx_dulce_arte.conf /etc/nginx/sites-available/dulce_arte
sudo ln -s /etc/nginx/sites-available/dulce_arte /etc/nginx/sites-enabled/dulce_arte
sudo rm /etc/nginx/sites-enabled/default
sudo chmod 755 /home/ubuntu
sudo nginx -t && sudo systemctl restart nginx
```

**Actualizar el servidor** con los últimos cambios de GitHub:

```bash
bash ~/dulce-arte/deploy/actualizar.sh
```

### Dominio y HTTPS

1. En [DuckDNS](https://www.duckdns.org) se creó el subdominio `dulcearte.duckdns.org` apuntando a la Elastic IP.
2. Certificado gratuito de Let's Encrypt (se renueva solo cada 90 días):

```bash
DOMINIO=dulcearte.duckdns.org
sudo mkdir -p /var/www/certbot
sudo cp deploy/nginx_dulce_arte.conf /etc/nginx/sites-available/dulce_arte
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot
sudo certbot certonly --webroot -w /var/www/certbot -d $DOMINIO --agree-tos -m <correo> --no-eff-email --deploy-hook "systemctl reload nginx"
sed "s/DOMINIO/$DOMINIO/g" deploy/nginx_dulce_arte_https.conf | sudo tee /etc/nginx/sites-available/dulce_arte > /dev/null
sudo nginx -t && sudo systemctl reload nginx
```

3. En el `.env` del servidor: `ALLOWED_HOSTS=dulcearte.duckdns.org,54.84.222.180`, `CSRF_TRUSTED_ORIGINS=https://dulcearte.duckdns.org` y `USAR_HTTPS=True`; luego `sudo systemctl restart gunicorn`.

## Apoyo de Inteligencia Artificial

El registro detallado de las consultas y apoyos solicitados a la IA está en [`prompts_ia.md`](prompts_ia.md).
