(function () {
  var sidebar = document.getElementById("sidebar");
  var scrim = document.getElementById("scrim");
  var btn = document.getElementById("menuBtn");
  if (!btn) return;
  function close() { sidebar.classList.remove("open"); scrim.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
  function toggle() {
    var open = sidebar.classList.toggle("open");
    scrim.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", String(open));
  }
  btn.addEventListener("click", toggle);
  scrim.addEventListener("click", close);
})();
