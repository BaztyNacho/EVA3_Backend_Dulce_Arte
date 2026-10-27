# Registro de apoyo de Inteligencia Artificial — Dulce Arte

Evaluación Parcial N°3 · Desarrollo Backend · INACAP
Autor: Bastian Sandoval

Este documento registra cómo se usó la IA durante el desarrollo: qué se le pidió, qué entregó, cómo se verificó y qué decisiones tomé yo. El código generado fue revisado, probado y explicado antes de incorporarlo al proyecto.

## 1. Herramientas utilizadas

| Herramienta | Uso |
|---|---|
| **Claude (chat, Anthropic)** | Herramienta usada en todo el backend, la interfaz inicial y el despliegue: análisis del enunciado, diseño de la arquitectura y del modelo de datos, generación de código paso a paso, depuración de errores y guía de despliegue en AWS. La IA ejecutaba y probaba el código en su propio entorno (incluidas pruebas en navegador con Playwright) antes de entregarlo. |
| **Claude Code** (instalado en Windows 11) | Instalado al inicio con los complementos Context7, Pro Workflow, Playwright CLI, Impeccable y Emil Kowalski. Hasta la entrega del backend y el despliegue **no se utilizó**: el trabajo se hizo completo desde el chat. Se reservó para la fase de ajustes visuales (ver sección 3.10). |

**Forma de trabajo acordada con la IA:**
- Avanzar paso a paso, con explicación de cada cambio para poder defenderlo.
- Recibir siempre archivos completos (no fragmentos) para evitar errores al copiar.
- Que la IA probara el código en su propio entorno antes de entregarlo.

## 2. Resumen por etapa

| Etapa | Qué se pidió a la IA | Resultado | Verificación |
|---|---|---|---|
| Planificación | Analizar el documento EVA_3_Backend y proponer un plan | Resumen de requerimientos y rúbrica, plan de 7 días | Revisado contra la rúbrica |
| Entorno | Instalar herramientas y configurar Django + PostgreSQL | Proyecto base con `.env` y PostgreSQL | `migrate` y Admin funcionando |
| Modelo de datos | Diseñar modelos para los 4 requerimientos | 12 modelos en 3 apps + diagrama ER | Pruebas de reglas con datos de ejemplo |
| Django Admin | Personalizar el Admin según la rúbrica | Filtros, búsquedas, inlines, template propio | 26 páginas del Admin probadas |
| Reglas de negocio | Descuento por receta, Kanban, cancelación, roles | Capa `services.py` + comando `crear_roles` | 15 casos de prueba |
| API REST | API con DRF y permisos por rol | ViewSets, acciones de negocio, Swagger | 49 pruebas automáticas |
| Interfaz web | Cotizador, Kanban, bodega, despachos con firma | App `web` con templates + JavaScript | Pruebas de punta a punta en navegador (escritorio y móvil) |
| Despliegue | Publicar en AWS EC2 | Gunicorn + Nginx + PostgreSQL en EC2 | Ensayo previo en Ubuntu y prueba real en la IP pública |
| Datos | Catálogo realista de pastelería | Comando `cargar_catalogo` (30 insumos, 11 productos, 18 extras) | Márgenes y vínculos revisados |

## 3. Registro detallado de consultas

### 3.1 Planificación y herramientas

**Prompt:** "Te enviaré un .doc con las instrucciones para este proyecto. Acorde a la temática y los requerimientos, indícame qué plugins y herramientas son las más indicadas."
- **Respuesta de la IA:** resumen de los 4 requerimientos del caso, de la rúbrica (60% proyecto y defensa, 40% prueba) y de los entregables. Propuso un plan de 7 días y las herramientas a usar (Context7, Playwright, Impeccable, django-environ, gitleaks, etc.). También descartó Supabase porque la base de datos debe correr dentro de la instancia EC2.
- **Mis decisiones:**
  - Reducir los roles a dos: **Administrador** (que cubre cocina, bodega y reparto) y **Atención y Ventas**. Así la interfaz es más simple y cabe en el plazo.
  - Confirmar las entregas con **firma y con foto** (ambas opciones).

### 3.2 Instalación y configuración del entorno

**Prompts:** "Al ejecutar `claude --version` me sale que el término no se reconoce" · "`psql` no se reconoce"
- **Respuesta:** diagnóstico de la variable PATH en Windows y comandos de PowerShell para corregirla.
- **Resultado:** Claude Code y PostgreSQL disponibles en la terminal.

**Prompt:** "Mi carpeta está en el Escritorio (OneDrive), quiero usar esa."
- **Respuesta:** propuso crear el entorno virtual **fuera de OneDrive**, para no sincronizar miles de archivos de librerías, y configurar VS Code para usarlo.
- **Aprendizaje:** qué es un entorno virtual y por qué no se versiona.

**Prompt:** "Las carpetas de los plugins quedaron en mi proyecto, ¿se suben a GitHub?"
- **Respuesta:** explicación del `.gitignore` y de qué archivos nunca deben subirse (`.env` con contraseñas, configuración local de herramientas).
- **Verificación:** antes del primer commit revisé que `.env` no apareciera en la lista de cambios.

**Prompt:** configuración de `settings.py` con variables de entorno y PostgreSQL.
- **Resultado:** `django-environ`, base de datos `db_dulce_arte` con un usuario dedicado (no el superusuario `postgres`), idioma es-cl y zona horaria America/Santiago.

### 3.3 Modelo de datos

**Prompt:** "Me parece muy buena estructura. Pedidos con 24 horas de anticipación. La personalización: un listado con opciones donde se puedan añadir cantidades, más o menos de un producto, y un cuadro de texto para un comentario extra."
- **Respuesta:** diagrama entidad-relación y 3 apps:
  - `inventario`: Insumo, Producto, RecetaItem (BOM), OpcionPersonalizacion, MovimientoInsumo.
  - `pedidos`: Cliente, Pedido, DetallePedido, PersonalizacionDetalle, HistorialEstado.
  - `despachos`: Ruta, Despacho.
- **Mi decisión:** porciones de −5 a +5 por extra, donde quitar no se cobra pero sí reduce el consumo de insumo.
- **Verificación:** la IA probó los modelos antes de entregarlos (total calculado de $81.000 en el caso de prueba, bloqueo de pedidos con menos de 24 horas, evidencia obligatoria en entregas).

**Prompt (posterior):** "Cada producto tendrá como mínimo 2 o 3 extras."
- **Respuesta:** detectó que los extras eran globales y agregó una relación muchos a muchos entre extras y productos (migración 0003). Además, la API y el Admin rechazan un extra que no corresponde al producto.

### 3.4 Django Admin

**Prompt:** personalizar el Admin para el nivel "Excelente" de la rúbrica.
- **Resultado:**
  - Filtros y búsquedas en todos los modelos, más un filtro propio de "stock bajo".
  - Etiquetas de color por estado y precios en formato chileno.
  - Receta editable dentro del producto.
  - Historial y movimientos de solo lectura.
  - Template `admin/base_site.html` con la identidad de Dulce Arte.
- **Verificación:** captura de pantalla del Admin y prueba de que una salida mayor al stock se rechaza.

**Prompt:** "Dame 3 insumos con precios, unidad, stock actual y mínimo; invéntame un producto."
- **Resultado:** datos de ejemplo para probar recetas y movimientos.

### 3.5 Reglas de negocio y roles

**Prompt:** continuar con la lógica del negocio.
- **Respuesta:** capa de servicios `pedidos/services.py`:
  - Calcula los insumos necesarios (receta + extras).
  - Confirma la cotización verificando y descontando stock dentro de una transacción atómica.
  - Avanza el Kanban sin saltar etapas.
  - Permite rechazar en control de calidad.
  - Cancela pedidos devolviendo insumos solo si no se empezó a preparar.
  - Agrega el comando `crear_roles` con los permisos de cada grupo.
- **Aprendizaje:** por qué las reglas van en una capa de servicios. El Admin, la API y la web usan las mismas funciones, así que no se pueden saltar.
- **Verificación:** 15 casos de prueba; por ejemplo, el pedido de 30 tortas sin stock se rechaza indicando qué falta.

### 3.6 API REST

**Prompt:** construir la API con DRF.
- **Resultado:**
  - Serializers que crean una cotización completa (productos y extras) en una sola petición.
  - Permisos por rol (`DjangoModelPermissions` y `EsAdministrador`).
  - Acciones: `confirmar`, `avanzar`, `rechazar-calidad`, `cancelar`, `disponibilidad`, `kanban`, `confirmar-entrega` (firma en base64 o foto).
  - Documentación Swagger en `/api/docs/`.
- **Verificación:** 49 pruebas automáticas con ambos roles. Por ejemplo, Ventas no puede mover el Kanban, una entrega sin firma ni foto se rechaza y un insumo en uso no se puede borrar.

### 3.7 Interfaz web

**Prompt:** construir la interfaz para ambos roles, visualmente atractiva y acorde a la temática.
- **Respuesta:** propuesta de dirección visual: paleta vainilla, frambuesa, chocolate y caramelo, tipografías Fraunces y Work Sans, y como elemento distintivo la "comanda" (ticket de pedido con borde perforado).
- **Resultado:**
  - Login, inicio por rol, lista de pedidos y cotizador con total en vivo.
  - Detalle con disponibilidad de stock antes de confirmar.
  - Kanban con arrastrar y soltar (SortableJS, incluido en el proyecto).
  - Bodega con medidores de stock.
  - Despachos con rutas y firma en pantalla programada en `<canvas>`.
- **Verificación:** pruebas de punta a punta con Playwright en escritorio y celular. Las capturas permitieron corregir: hora en formato 24 horas, columnas del Kanban cortadas, una caja vacía visible en móvil y mensajes de error que no se limpiaban.
- **Mi decisión:** dejar mis ajustes visuales para el final, priorizando completar la rúbrica y el despliegue.

### 3.8 Despliegue en AWS EC2

**Prompt:** guiar el despliegue en AWS Academy.
- **Respuesta:**
  - Preparó `settings.py` para producción (`STATIC_ROOT`, `CSRF_TRUSTED_ORIGINS`, protecciones de seguridad).
  - Creó el servicio de Gunicorn, la configuración de Nginx y el script `deploy/actualizar.sh`.
  - Antes de entregarlos, hizo un **ensayo completo en un servidor Ubuntu**, que detectó un error 502 por permisos del socket de Gunicorn. Se corrigió con `UMask=0007`.
- **Problemas resueltos durante el despliegue real:**
  - El repositorio privado impedía clonarlo, así que lo hice público tras verificar que no tuviera secretos.
  - Faltaba el nombre de la carpeta de destino en `git clone`.
  - Compartí por error la `SECRET_KEY` en el chat; la IA recomendó rotarla y la cambié.
- **Resultado:** aplicación funcionando en http://54.84.222.180/ (Elastic IP), con PostgreSQL en la misma instancia.

**Prompt:** "Dame un listado de 10 nuevos productos de repostería, con los insumos necesarios y 2 o 3 extras por producto; precios y cantidades a tu criterio considerando valores chilenos."
- **Resultado:** comando `cargar_catalogo`, con 30 insumos, 11 productos con receta y 18 extras. Es reutilizable en local y en el servidor sin duplicar datos.

### 3.9 Nuevas funciones: catálogo, tiempos e imágenes

**Prompt:** lista de ajustes propia. Para Atención y Ventas, un **Catálogo** con nombre, descripción, ingredientes, precio y tiempo de preparación de cada producto. Para el Administrador: confirmación al mover pedidos en Cocina, Bodega en tarjetas con imagen y botones para agregar o registrar mermas, y el Admin con la temática del proyecto (sin cambiar sus funciones).
- **Respuesta de la IA:** clasificó la lista en cambios de backend y cambios solo visuales. Los de backend (los hizo en el chat, con pruebas):
  - Campo `tiempo_preparacion` (minutos, informativo) en Producto y campo `imagen` en Insumo, con la migración 0004.
  - Página `/catalogo/` solo para Atención y Ventas, con imagen o reemplazo elegante (inicial sobre color) cuando no hay foto.
  - Botón "Cotizar este producto" que abre el cotizador con el producto ya agregado.
  - `CLAUDE.md` actualizado y una guía de prompts para hacer lo visual en Claude Code.
- **Mis decisiones:**
  - El tiempo de preparación es solo informativo, no cambia la regla de 24 horas.
  - El catálogo es solo para Ventas, como apoyo para atender al cliente.
  - En la bodega se registran tanto entradas como mermas.
  - Las fotos de insumos y productos las tomo yo.

### 3.10 Uso de Claude Code (pendiente)

**Prompt:** "Dentro de todo lo que hemos realizado, ¿en qué momento utilizamos Claude Code? Inicialmente solicité herramientas y plugins de diseño para que la página se viera profesional, con animaciones y transiciones."
- **Respuesta de la IA:** reconoció que Claude Code y sus complementos no se habían usado, ya que todo se hizo desde el chat, y que debió avisarlo cuando cambió la forma de trabajo. Propuso usar Claude Code en la fase de ajustes visuales, porque ahí aporta más: trabaja directo sobre los archivos, ve la página en `localhost` con Playwright CLI, audita el diseño con Impeccable y aplica animaciones con Emil Kowalski.
- **Mi decisión:** *(completar al terminar la fase visual con lo que se hizo en Claude Code).*

## 4. Aprendizajes y criterio propio

- **La IA aceleró mucho la escritura de código**, pero las decisiones del negocio fueron mías: los roles, la regla de 24 horas, el sistema de extras, firma y foto, el catálogo y la prioridad entre funcionalidad y diseño.
- **Probar antes de confiar:** cada entrega se acompañó de pruebas automáticas o capturas. Varias detectaron errores reales (el 502 de Gunicorn, problemas visuales en móvil).
- **Seguridad:** aprendí a separar los secretos del código (`.env`), a no compartir claves, a usar un usuario de base de datos dedicado y a explicar por qué el sitio no tiene HTTPS sin un dominio propio.
- **Arquitectura:** entendí el recorrido Nginx → Gunicorn → Django → PostgreSQL y por qué `runserver` no se usa en producción.
- **Límites de la IA:** a veces necesitó aclaraciones mías (por ejemplo, que los extras debían ser distintos por producto), y sus primeras versiones de la interfaz tuvieron detalles que corregimos tras revisarlas. También aprendí a revisar que las herramientas que pedí se usaran de verdad: los plugins de diseño quedaron instalados pero sin uso hasta que pregunté por ellos.
