// Portada de Trazora: modo claro/oscuro (misma clave que la app) y la reserva de horarios de ejemplo.
(function () {
  var root = document.documentElement;
  try { var guardado = localStorage.getItem('trazora_tema'); if (guardado === 'light' || guardado === 'dark') root.setAttribute('data-theme', guardado); } catch (e) {}
  document.getElementById('tema').addEventListener('click', function () {
    var actual = root.getAttribute('data-theme');
    var oscuro = actual ? actual === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    var nuevo = oscuro ? 'light' : 'dark';
    root.setAttribute('data-theme', nuevo);
    try { localStorage.setItem('trazora_tema', nuevo); } catch (e) {}
  });

  var caja = document.getElementById('slots'), mensaje = document.getElementById('slotmsg');
  var horas = ['08:00', '08:30', '09:00', '09:30', '10:00', '10:30', '11:00', '11:30'];
  var tomadas = { '10:00': 'Colegio Paredes' };
  function fin(h) { return h.slice(3) === '00' ? h.slice(0, 3) + '30' : String(+h.slice(0, 2) + 1).padStart(2, '0') + ':00'; }
  horas.forEach(function (h) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'slot';
    b.innerHTML = '<span>' + h + '</span><small></small>';
    function pintar() {
      var t = tomadas[h];
      b.classList.toggle('on', !!t);
      b.querySelector('small').textContent = t || 'Libre';
      b.setAttribute('aria-pressed', t ? 'true' : 'false');
    }
    b.addEventListener('click', function () {
      if (tomadas[h]) {
        mensaje.textContent = h + ' ya está reservada (' + tomadas[h] + '). Elige otra hora.';
        mensaje.className = 'slotmsg bad';
        b.classList.remove('shake'); void b.offsetWidth; b.classList.add('shake');
        return;
      }
      tomadas[h] = 'Clínica Rojas'; pintar();
      mensaje.textContent = 'Reservaste ' + h + '–' + fin(h) + '. Si otro coordinador la pide ahora, verá que ya no está libre.';
      mensaje.className = 'slotmsg';
    });
    pintar(); caja.appendChild(b);
  });
})();
