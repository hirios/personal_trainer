/**
 * toast.js — Sistema de notificações toast do FitFlow Pro.
 * Uso: Toast.success("Salvo!") | Toast.error("Erro!") | Toast.warning("Atenção") | Toast.info("Info")
 * Auto-fecha em 4s com barra de progresso. Animação suave de entrada e saída.
 */

const Toast = (() => {
  // Garante que o container existe no DOM
  function _getContainer() {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.setAttribute("aria-live", "polite");
      container.setAttribute("aria-atomic", "false");
      // Posicionamento via estilo inline para não depender de classes externas
      container.style.cssText = `
        position: fixed;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 8px;
        pointer-events: none;
      `;
      // Desktop: canto inferior direito / Mobile: centralizado na base
      _applyContainerPosition(container);
      document.body.appendChild(container);

      // Reposiciona ao redimensionar
      window.addEventListener("resize", () => _applyContainerPosition(container));
    }
    return container;
  }

  function _applyContainerPosition(container) {
    if (window.innerWidth >= 768) {
      container.style.bottom = "24px";
      container.style.right = "24px";
      container.style.left = "auto";
      container.style.transform = "none";
      container.style.alignItems = "flex-end";
    } else {
      container.style.bottom = "80px"; // acima da bottom nav
      container.style.left = "50%";
      container.style.right = "auto";
      container.style.transform = "translateX(-50%)";
      container.style.alignItems = "center";
      container.style.width = "calc(100vw - 32px)";
    }
  }

  const CONFIGS = {
    success: {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>`,
      color: "#22C55E",
      bg: "#F0FDF4",
      border: "#BBF7D0",
      text: "#15803D",
    },
    error: {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
      color: "#EF4444",
      bg: "#FEF2F2",
      border: "#FECACA",
      text: "#B91C1C",
    },
    warning: {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
      color: "#F97316",
      bg: "#FFF7ED",
      border: "#FED7AA",
      text: "#C2410C",
    },
    info: {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
      color: "#3B82F6",
      bg: "#EFF6FF",
      border: "#BFDBFE",
      text: "#1D4ED8",
    },
  };

  const DURATION = 4000; // ms

  function _show(type, message) {
    const container = _getContainer();
    const cfg = CONFIGS[type];

    const toast = document.createElement("div");
    toast.style.cssText = `
      display: flex;
      align-items: flex-start;
      gap: 10px;
      padding: 12px 16px;
      background: ${cfg.bg};
      border: 1px solid ${cfg.border};
      border-radius: 12px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.08);
      min-width: 280px;
      max-width: 380px;
      pointer-events: all;
      position: relative;
      overflow: hidden;
      opacity: 0;
      transform: translateY(8px);
      transition: opacity 0.22s ease, transform 0.22s ease;
      cursor: pointer;
    `;

    toast.innerHTML = `
      <span style="color:${cfg.color};flex-shrink:0;margin-top:1px;">${cfg.icon}</span>
      <span style="font-family:'DM Sans',sans-serif;font-size:14px;font-weight:500;color:${cfg.text};flex:1;line-height:1.4;">${_escape(message)}</span>
      <button onclick="this.closest('[data-toast]').remove()" style="background:none;border:none;cursor:pointer;padding:0;color:${cfg.color};opacity:0.6;flex-shrink:0;line-height:1;">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
      <div style="
        position:absolute;bottom:0;left:0;height:3px;
        background:${cfg.color};opacity:0.35;border-radius:0 0 0 12px;
        width:100%;
        animation: toast-progress ${DURATION}ms linear forwards;
      "></div>
    `;

    toast.setAttribute("data-toast", type);

    // Fecha ao clicar
    toast.addEventListener("click", () => _dismiss(toast));

    // Injeta keyframe de progresso se necessário
    if (!document.getElementById("toast-styles")) {
      const style = document.createElement("style");
      style.id = "toast-styles";
      style.textContent = `
        @keyframes toast-progress {
          from { width: 100%; }
          to { width: 0%; }
        }
      `;
      document.head.appendChild(style);
    }

    container.appendChild(toast);

    // Anima entrada
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";
      });
    });

    // Auto-fecha após DURATION ms
    const timer = setTimeout(() => _dismiss(toast), DURATION);
    toast._timer = timer;

    return toast;
  }

  function _dismiss(toast) {
    clearTimeout(toast._timer);
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 250);
  }

  function _escape(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

  return {
    success: (msg) => _show("success", msg),
    error: (msg) => _show("error", msg),
    warning: (msg) => _show("warning", msg),
    info: (msg) => _show("info", msg),
  };
})();
