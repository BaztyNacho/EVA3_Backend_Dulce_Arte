/*
 * Tarjeta del usuario (esquina superior derecha).
 * Se abre y cierra con el botón; también se cierra con Escape o al hacer clic fuera.
 */
(() => {
  const boton = document.querySelector('.usuario__boton');
  const tarjeta = document.getElementById('usuario-tarjeta');
  if (!boton || !tarjeta) return;

  function abrir(abierta) {
    tarjeta.hidden = !abierta;
    boton.setAttribute('aria-expanded', String(abierta));
  }

  boton.addEventListener('click', () => abrir(tarjeta.hidden));
  document.addEventListener('click', (evento) => {
    if (!tarjeta.hidden && !evento.target.closest('.usuario')) abrir(false);
  });
  document.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape' && !tarjeta.hidden) {
      abrir(false);
      boton.focus();
    }
  });
})();
