# Guía: ajustes visuales de Dulce Arte con Claude Code

Esta guía es para ti; **no se sube al repositorio**. Contiene los prompts para copiar y pegar en Claude Code, en orden.

## Antes de empezar

1. Abre VS Code en tu proyecto y, en la terminal, activa el entorno y levanta el servidor:
   ```powershell
   python manage.py runserver
   ```
2. Abre una **segunda terminal** (el `+` del panel de terminal), entra a la carpeta del proyecto y escribe `claude`.
3. Claude Code leerá solo el `CLAUDE.md` con todo el contexto del proyecto.

**Cómo trabajar:**
- Una tarea por vez. Revisa el resultado en tu navegador antes de pasar a la siguiente.
- Cuando Claude Code te pida permiso para editar un archivo o ejecutar un comando, lee qué hará antes de aceptar.
- Si algo no te gusta, díselo con tus palabras: *"el botón quedó muy grande"*, *"prefiero el color frambuesa"*.
- **Haz commit en GitHub Desktop después de cada tarea que funcione.** Si algo sale mal, puedes volver atrás.
- Guarda los prompts que uses y lo que respondió: es la evidencia para el `prompts_ia.md` (sección 3.10).

---

## Tarea 0 · Configurar Impeccable (una sola vez)

```
/impeccable init
```

Impeccable te hará preguntas sobre el producto. Respuestas sugeridas:
- **Producto:** sistema interno de pedidos para una pastelería artesanal chilena (Dulce Arte). Lo usan vendedores en el mostrador y el administrador en cocina, bodega y reparto.
- **Tono:** cálido, artesanal y profesional. Elegante pero fácil de usar.
- **Identidad existente:** paleta vainilla, frambuesa, chocolate y caramelo. Tipografías Fraunces y Work Sans. Elemento distintivo: la comanda (ticket con borde perforado). Todo está en `web/static/web/css/dulce.css`.

---

## Tarea 1 · Auditoría de diseño (no cambia nada)

```
Usa Impeccable para auditar el diseño de la interfaz web (templates en web/templates/web/ y web/static/web/css/dulce.css). No modifiques nada todavía: dame un informe priorizado de qué mejorar en jerarquía visual, espaciado, consistencia y accesibilidad, respetando la identidad descrita en CLAUDE.md.
```

Lee el informe y decide qué sugerencias aplicar. Puedes pedirle: *"aplica las sugerencias 1, 3 y 4"*.

---

## Tarea 2 · Cocina: confirmar antes de mover un pedido

```
En la Cocina (web/templates/web/kanban.html y web/static/web/js/kanban.js) quiero evitar mover un pedido por accidente. Cada vez que se mueva un pedido de una etapa a otra (arrastrando o con el botón), debe aparecer una ventana en el centro de la pantalla que confirme la acción y muestre el detalle: número de pedido, cliente, productos, la etapa actual y la etapa nueva. Debe tener los botones "Confirmar" y "Cancelar". Si se cancela, la tarjeta vuelve a su columna original sin llamar a la API. Lo mismo para "Rechazar" en Control de Calidad (que ya pide un motivo).

Requisitos:
- Ventana accesible: role="dialog", aria-modal, foco dentro de la ventana, Escape y clic fuera cancelan, Enter confirma.
- Usa la skill de Emil Kowalski para la animación de apertura y cierre (corta, sin ease-in, sin scale(0)) y respeta prefers-reduced-motion.
- Mantén la identidad visual (variables de dulce.css).
- No cambies la API ni el backend.
- Al terminar, prueba con Playwright CLI: mover una tarjeta, cancelar (debe volver) y confirmar (debe avanzar).
```

---

## Tarea 3 · Bodega en tarjetas con imagen

```
Rediseña la Bodega (web/templates/web/bodega.html, web/static/web/js/bodega.js y dulce.css). Hoy es una lista larga. Quiero una grilla de tarjetas, una por insumo:
- Arriba el nombre del insumo.
- Al centro su imagen. Usa el include web/_imagen.html, que ya muestra un reemplazo elegante si no hay foto.
- Abajo la cantidad actual con su unidad, destacando en rojo si está bajo el mínimo (insumo.stock_bajo), y el mínimo en texto pequeño.
- Dos botones por tarjeta: "Agregar al inventario" y "Registrar merma". Cada uno abre una ventana pequeña con los campos Cantidad y Motivo, que envía a POST /api/movimientos-insumo/ (tipo "entrada" o "ajuste"), y luego actualiza la tarjeta y muestra un aviso con mostrarAviso().
- Mantén los filtros "Todos / Stock bajo" y la sección "Últimos movimientos".
- El formulario general de la derecha ya no es necesario: elimínalo.

Requisitos: diseño con Impeccable, ventana accesible (role="dialog", Escape, foco), responsivo (2 columnas en celular), animaciones sutiles con Emil Kowalski. No cambies el backend. Prueba con Playwright CLI: agregar stock, registrar una merma y una merma mayor al stock (debe mostrar el error de la API).
```

---

## Tarea 4 · Catálogo con más presencia

```
Mejora el diseño del Catálogo (web/templates/web/catalogo.html y dulce.css) para que se vea como una vitrina de pastelería, manteniendo una sola columna y la información actual: imagen, categoría, nombre, descripción, ingredientes, extras con su precio, precio y tiempo de preparación, y el botón "Cotizar este producto". El vendedor lo usará frente al cliente, así que debe ser fácil de leer de un vistazo. Usa Impeccable. No cambies la vista ni el backend.
```

---

## Tarea 5 · Administración con la temática de Dulce Arte

```
Quiero que el Django Admin (/admin/) tenga la temática visual de Dulce Arte, igual que la interfaz web: tipografías Fraunces y Work Sans, paleta de dulce.css, botones redondeados, tablas y formularios más limpios, y la barra superior en chocolate. Hoy solo cambiamos colores en templates/admin/base_site.html.

Reglas estrictas:
- Solo cambios visuales: CSS y templates dentro de templates/admin/. Puedes crear templates/admin/... que extiendan los de Django.
- NO modifiques ningún admin.py, ni quites o cambies funcionalidades del Admin (filtros, búsquedas, acciones, inlines, permisos, historial).
- Debe seguir funcionando el modo oscuro del Admin.

Revisa con Playwright CLI estas páginas: el índice, la lista de pedidos (con filtros y acciones), el formulario de un producto con su receta, la lista de insumos y la página de login del Admin. Usa Impeccable para el diseño.
```

---

## Tarea 6 · Animaciones y transiciones generales

```
Usa la skill de Emil Kowalski para revisar toda la interfaz web y proponer animaciones y transiciones que la hagan sentir más pulida: estados hover y active de botones, aparición de avisos, apertura de ventanas, cambio de pestañas, carga de tarjetas en el Kanban, etc. Primero dame la lista de propuestas con el porqué de cada una; después aplicaremos las que yo elija. Deben ser cortas, con propósito y respetar prefers-reduced-motion.
```

---

## Tarea 7 · Revisión final

```
Con Playwright CLI recorre la aplicación completa como Administrador y como Atención y Ventas (te daré las contraseñas), en escritorio y en celular (390 px de ancho). Revisa que no haya errores en la consola, que todo se vea bien y que los flujos funcionen: cotizar, confirmar, mover en cocina con confirmación, bodega, despachos con firma y catálogo. Entrégame un informe con lo que encuentres.
```

---

## Al terminar

1. Commit y push en GitHub Desktop.
2. Actualiza el servidor: `bash ~/dulce-arte/deploy/actualizar.sh`
3. Envíame un resumen de lo que hiciste en Claude Code y completamos la sección 3.10 del `prompts_ia.md`.
