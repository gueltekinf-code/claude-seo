/* Aquastreet: mobiles Menü + Live-Öffnungsstatus. Ohne Abhängigkeiten, ohne Tracking. */
(function () {
  "use strict";

  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  // Öffnungszeiten Waschstraße (Europe/Berlin). 0 = Sonntag.
  var HOURS = { 0: [10, 18], 1: [8, 20], 2: [8, 20], 3: [8, 20], 4: [8, 20], 5: [8, 20], 6: [8, 20] };
  var DAYS = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];

  function berlinNow() {
    try {
      var parts = new Intl.DateTimeFormat("en-GB", {
        timeZone: "Europe/Berlin", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false
      }).formatToParts(new Date());
      var map = {};
      parts.forEach(function (p) { map[p.type] = p.value; });
      var wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(map.weekday);
      return { day: wd, mins: parseInt(map.hour, 10) % 24 * 60 + parseInt(map.minute, 10) };
    } catch (e) {
      var d = new Date();
      return { day: d.getDay(), mins: d.getHours() * 60 + d.getMinutes() };
    }
  }

  function pad(h) { return (h < 10 ? "0" : "") + h + ":00"; }

  function status() {
    var n = berlinNow();
    var h = HOURS[n.day];
    if (n.mins >= h[0] * 60 && n.mins < h[1] * 60) {
      return { open: true, text: "Waschstraße geöffnet · bis " + pad(h[1]) + " Uhr" };
    }
    if (n.mins < h[0] * 60) {
      return { open: false, text: "Waschstraße öffnet heute um " + pad(h[0]) + " Uhr · SB 24/7" };
    }
    var next = (n.day + 1) % 7;
    return { open: false, text: "Waschstraße öffnet " + (next === (n.day + 1) % 7 ? "morgen" : DAYS[next]) + " um " + pad(HOURS[next][0]) + " Uhr · SB 24/7" };
  }

  var s = status();
  document.querySelectorAll("[data-status]").forEach(function (el) {
    el.textContent = s.text;
    el.classList.add(s.open ? "is-open" : "is-closed");
  });

  // Heutigen Tag in Öffnungszeiten-Tabellen hervorheben
  var today = berlinNow().day;
  document.querySelectorAll("[data-day~='" + today + "']").forEach(function (row) {
    row.classList.add("is-today");
  });
})();
