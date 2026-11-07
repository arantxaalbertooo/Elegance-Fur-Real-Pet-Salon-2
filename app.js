/* Elegance Fur Real CRM Hub - small UI helpers (dialogs, prefill, booking totals). No libraries needed. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);

  // ---------- dialogs ----------
  function fill(form, values) {
    Object.keys(values || {}).forEach((name) => {
      const v = values[name];
      const els = form.querySelectorAll('[name="' + name + '"]');
      els.forEach((el) => {
        if (el.type === "checkbox") {
          el.checked = Array.isArray(v) ? v.map(String).includes(el.value) : !!v && v !== "0";
        } else if (el.type !== "file") {
          el.value = v == null ? "" : v;
          if (el.tagName === "SELECT") el.dispatchEvent(new Event("change"));
        }
      });
    });
  }

  function openDialog(trigger) {
    const d = $(trigger.dataset.dialog);
    if (!d) return;
    const f = d.querySelector("form");
    f.reset();
    f.action = trigger.dataset.action || f.dataset.defaultAction || f.action;
    const h = d.querySelector("[data-title]");
    if (h) h.textContent = trigger.dataset.title || h.dataset.defaultTitle || h.textContent;
    const sb = f.querySelector('button[type="submit"]');
    if (sb) sb.textContent = trigger.dataset.submit || sb.dataset.defaultText || sb.textContent;
    f.querySelectorAll('input[type="hidden"][data-clear]').forEach((i) => (i.value = ""));
    fill(f, trigger.dataset.values ? JSON.parse(trigger.dataset.values) : {});
    d.dispatchEvent(new CustomEvent("dialog-open"));
    d.showModal();
  }

  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-dialog]");
    if (t) { e.preventDefault(); openDialog(t); return; }
    const c = e.target.closest("[data-close-dialog]");
    if (c) c.closest("dialog").close();
    if (e.target.tagName === "DIALOG") e.target.close();        // click on the backdrop
  });

  document.querySelectorAll("dialog form").forEach((f) => {
    f.dataset.defaultAction = f.getAttribute("action") || "";
    const h = f.querySelector("[data-title]"); if (h) h.dataset.defaultTitle = h.textContent;
    const sb = f.querySelector('button[type="submit"]'); if (sb) sb.dataset.defaultText = sb.textContent;
  });

  // ---------- booking dialog: pets follow the chosen customer, live total ----------
  const bd = $("apptDialog");
  if (bd) {
    const cust = bd.querySelector('[name="customer_id"]'), pet = bd.querySelector('[name="pet_id"]');
    const allPets = Array.from(pet.options).map((o) => ({ v: o.value, t: o.textContent, c: o.dataset.c }));
    const showPets = () => {
      const keep = pet.value;
      pet.innerHTML = "";
      allPets.filter((p) => !p.v || p.c === cust.value).forEach((p) => {
        const o = document.createElement("option"); o.value = p.v; o.textContent = p.v ? p.t : "— no pet on file —"; pet.appendChild(o);
      });
      pet.value = keep && Array.from(pet.options).some((o) => o.value === keep) ? keep : (pet.options[1] ? pet.options[1].value : "");
    };
    const total = () => {
      let price = 0, mins = 0;
      bd.querySelectorAll('input[name="services"]:checked').forEach((c) => { price += +c.dataset.price; mins += +c.dataset.min; });
      const t = bd.querySelector('[name="time"]').value; let end = "";
      if (t && mins) { const [h, m] = t.split(":").map(Number), e = h * 60 + m + mins; end = " · ends about " + ((Math.floor(e / 60) + 11) % 12 + 1) + ":" + String(e % 60).padStart(2, "0") + (e >= 720 && e < 1440 ? " PM" : " AM"); }
      $("bookingTotal").textContent = mins ? "Total ₱" + price.toLocaleString() + " · " + mins + " min" + end : "Choose at least one service.";
    };
    cust.addEventListener("change", showPets);
    bd.addEventListener("change", (e) => { if (e.target.name === "services" || e.target.name === "time") total(); });
    bd.addEventListener("dialog-open", () => {
      showPets(); total();
      const dt = bd.querySelector('[name="date"]');
      if (!dt.value) { const t = new Date(); t.setDate(t.getDate() + 1); dt.value = t.getFullYear() + "-" + String(t.getMonth() + 1).padStart(2, "0") + "-" + String(t.getDate()).padStart(2, "0"); }
    });
    bd.addEventListener("recalc", total);
  }

  // ---------- login ----------
  const tp = $("togglePassword");
  if (tp) tp.addEventListener("click", () => {
    const i = $("loginPassword"), show = i.type === "password";
    i.type = show ? "text" : "password"; tp.textContent = show ? "Hide" : "Show"; tp.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });

  // ---------- misc ----------
  document.querySelectorAll("[data-autosubmit]").forEach((s) => s.addEventListener("change", () => s.form.submit()));
  const mm = $("mobileMenuBtn"), sb = $("sidebar");
  if (mm && sb) mm.addEventListener("click", () => { const o = sb.classList.toggle("open"); mm.setAttribute("aria-expanded", String(o)); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sb) sb.classList.remove("open"); });
  document.querySelectorAll("[data-confirm]").forEach((f) => f.addEventListener("submit", (e) => { if (!confirm(f.dataset.confirm)) e.preventDefault(); }));
  document.querySelectorAll("[data-history]").forEach((b) => b.addEventListener("click", () => {
    const box = $("history-" + b.dataset.history), hidden = box.classList.toggle("hidden");
    b.textContent = hidden ? b.dataset.label + " →" : "Hide history ↑";
  }));
  const region = $("noticeRegion");
  if (region && region.children.length) setTimeout(() => (region.innerHTML = ""), 6500);
  // open a dialog straight from a link such as /appointments?open=apptDialog&service=3
  const params = new URLSearchParams(location.search);
  if (params.get("open") && $(params.get("open"))) {
    const d = $(params.get("open"));
    d.dispatchEvent(new CustomEvent("dialog-open"));
    if (params.get("service")) d.querySelectorAll('input[name="services"]').forEach((c) => { if (c.value === params.get("service")) c.checked = true; });
    d.dispatchEvent(new CustomEvent("recalc"));
    d.showModal();
    history.replaceState(null, "", location.pathname);
  }

})();
