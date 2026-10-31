/*
 * Inicio: abre la ventana con todas las próximas entregas.
 * Se usa el elemento <dialog> del navegador (foco dentro y cierre con Escape).
 */
const ventanaEntregas = document.getElementById('ventana-entregas');

document.querySelectorAll('[data-abrir-entregas]').forEach((boton) => {
  boton.addEventListener('click', () => ventanaEntregas.showModal());
});

ventanaEntregas.querySelector('[data-cerrar]').addEventListener('click', () => ventanaEntregas.close());

// Clic en el fondo oscuro (fuera de la ventana) también la cierra
ventanaEntregas.addEventListener('click', (evento) => {
  if (esClicFuera(evento, ventanaEntregas)) ventanaEntregas.close();
});
