// Accessible tab strip shared by the multi-mode tools (money, dates, random picker).
// Markup: a [role=tablist] holding [role=tab] buttons whose aria-controls names a
// [role=tabpanel]. Each tab may carry data-hash ("emi") so /page/#emi deep-links to it.

export function tabs(list: HTMLElement, onChange?: (id: string) => void): (i: number) => void {
  const ts = [...list.querySelectorAll<HTMLButtonElement>("[role=tab]")];
  const select = (i: number, push = false) => {
    ts.forEach((t, k) => {
      const on = k === i;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      const panel = document.getElementById(t.getAttribute("aria-controls") || "");
      if (panel) panel.hidden = !on;
    });
    const h = ts[i].dataset.hash;
    if (push && h) history.replaceState(null, "", `#${h}`);
    onChange?.(ts[i].getAttribute("aria-controls") || "");
  };
  ts.forEach((t, i) => {
    t.addEventListener("click", () => select(i, true));
    t.addEventListener("keydown", (e) => {
      let j = -1;
      if (e.key === "ArrowRight") j = (i + 1) % ts.length;
      else if (e.key === "ArrowLeft") j = (i - 1 + ts.length) % ts.length;
      else if (e.key === "Home") j = 0;
      else if (e.key === "End") j = ts.length - 1;
      if (j < 0) return;
      e.preventDefault();
      select(j, true);
      ts[j].focus();
    });
  });
  const fromHash = () => {
    const i = ts.findIndex((t) => t.dataset.hash && `#${t.dataset.hash}` === location.hash);
    select(i >= 0 ? i : 0);
  };
  fromHash();
  window.addEventListener("hashchange", fromHash);
  return (i: number) => select(i, true);
}
