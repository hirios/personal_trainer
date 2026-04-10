/**
 * layout.js — Componente de layout compartilhado do FitFlow Pro (área do trainer).
 * Renderiza sidebar (desktop), bottom nav (mobile) e header com breadcrumb.
 *
 * Uso em cada página:
 *   <script src="/frontend/js/components/layout.js"></script>
 *   <script>
 *     document.addEventListener('DOMContentLoaded', () => {
 *       initLayout("Nome da Página", [
 *         { label: "Dashboard", href: "/frontend/trainer/index.html" },
 *         { label: "Nome da Página" }
 *       ]);
 *     });
 *   </script>
 */

// ─── Anti-FOUC ────────────────────────────────────────────────────────────────
// Este bloco executa SINCRONAMENTE quando o script é parseado (ainda no <head>),
// antes de o browser renderizar o body. Oculta o body até que initLayout()
// injete a sidebar e então o revela com um fade-in suave, eliminando o flicker.
(function () {
  const shield = document.createElement("style");
  shield.id = "layout-fouc-shield";
  shield.textContent = "body { opacity: 0; transition: opacity 0.15s ease; }";
  document.head.appendChild(shield);
})();

// Definição dos itens de navegação do trainer
const NAV_ITEMS = [
  {
    id: "students",
    label: "Alunos",
    href: "/frontend/trainer/index.html",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  },
  {
    id: "schedule",
    label: "Agenda",
    href: "/frontend/trainer/schedule/index.html",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
  },
  {
    id: "financial",
    label: "Financeiro",
    href: "/frontend/trainer/payments/index.html",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`,
  },
  {
    id: "profile",
    label: "Perfil",
    href: "/frontend/trainer/profile.html",
    icon: `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
  },
];

/**
 * Detecta qual item de nav está ativo com base na URL atual.
 */
function _getActiveNavId() {
  const path = window.location.pathname;
  // Rotas que mapeiam para "students"
  if (path.includes("/trainer/index") || path.includes("/trainer/students")) {
    return "students";
  }
  for (const item of NAV_ITEMS) {
    if (path.includes(item.href.split("/").pop().replace(".html", ""))) {
      return item.id;
    }
  }
  return "students";
}

/**
 * Renderiza a sidebar fixa para desktop (lg+).
 */
function _renderSidebar(user) {
  const activeId = _getActiveNavId();
  const avatarInitials = (user?.name || "?")
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();

  const navItemsHTML = NAV_ITEMS.map((item) => {
    const isActive = item.id === activeId;
    return `
      <a href="${item.href}"
         class="nav-item${isActive ? " nav-item-active" : ""}"
         aria-current="${isActive ? "page" : "false"}">
        <span class="nav-icon">${item.icon}</span>
        <span class="nav-label">${item.label}</span>
      </a>
    `;
  }).join("");

  return `
    <aside id="sidebar" role="navigation" aria-label="Menu principal">
      <!-- Logo -->
      <div class="sidebar-logo">
        <a href="/frontend/trainer/index.html" class="logo-link">
          <div class="logo-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>
          </div>
          <span class="logo-text">FitFlow <strong>Pro</strong></span>
        </a>
      </div>

      <!-- Navegação -->
      <nav class="sidebar-nav">
        ${navItemsHTML}
      </nav>

      <!-- Avatar do trainer na base -->
      <div class="sidebar-footer">
        <div class="trainer-avatar-wrap">
          ${
            user?.avatar_url
              ? `<img src="${user.avatar_url}" alt="${user.name}" class="trainer-avatar-img"/>`
              : `<div class="trainer-avatar-initials">${avatarInitials}</div>`
          }
          <div class="trainer-info">
            <span class="trainer-name">${user?.name || "Trainer"}</span>
            <span class="trainer-plan">${_planLabel(user?.plan)}</span>
          </div>
        </div>
        <button onclick="Auth.logout()" class="logout-btn" title="Sair">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        </button>
      </div>
    </aside>
  `;
}

/**
 * Renderiza a bottom navigation fixa para mobile.
 */
function _renderBottomNav() {
  const activeId = _getActiveNavId();

  const itemsHTML = NAV_ITEMS.map((item) => {
    const isActive = item.id === activeId;
    return `
      <a href="${item.href}" class="bottom-nav-item${isActive ? " bottom-nav-active" : ""}">
        ${item.icon}
        <span>${item.label}</span>
      </a>
    `;
  }).join("");

  return `
    <nav id="bottom-nav" role="navigation" aria-label="Navegação mobile">
      ${itemsHTML}
    </nav>
  `;
}

/**
 * Renderiza o header com breadcrumb e título da página.
 */
function _renderHeader(pageTitle, breadcrumbs = []) {
  const breadcrumbHTML = breadcrumbs
    .map((crumb, i) => {
      const isLast = i === breadcrumbs.length - 1;
      if (isLast) {
        return `<span class="breadcrumb-current">${crumb.label}</span>`;
      }
      return `
        <a href="${crumb.href}" class="breadcrumb-link">${crumb.label}</a>
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      `;
    })
    .join("");

  return `
    <header id="main-header">
      <div class="header-left">
        <!-- Breadcrumb (desktop) -->
        ${breadcrumbs.length > 0 ? `<nav class="breadcrumb" aria-label="Breadcrumb">${breadcrumbHTML}</nav>` : ""}
        <h1 class="page-title">${pageTitle}</h1>
      </div>
      <div class="header-right" id="header-actions">
        <!-- Ações específicas da página são injetadas aqui -->
      </div>
    </header>
  `;
}

/**
 * Injeta os estilos do layout.
 */
function _injectLayoutStyles() {
  if (document.getElementById("layout-styles")) return;
  const style = document.createElement("style");
  style.id = "layout-styles";
  style.textContent = `
    /* Reset base */
    *, *::before, *::after { box-sizing: border-box; }

    /* Sidebar */
    #sidebar {
      position: fixed; left: 0; top: 0; bottom: 0;
      width: 256px; background: #fff;
      border-right: 1px solid #E2E8F0;
      display: none; /* oculto no mobile */
      flex-direction: column;
      z-index: 100;
    }
    @media (min-width: 1024px) {
      #sidebar { display: flex; }
      #main-content { margin-left: 256px; }
    }

    .sidebar-logo {
      padding: 24px 20px 20px;
      border-bottom: 1px solid #F1F5F9;
    }
    .logo-link {
      display: flex; align-items: center; gap: 10px;
      text-decoration: none;
    }
    .logo-icon {
      width: 38px; height: 38px; border-radius: 10px;
      background: #22C55E;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }
    .logo-text {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 18px; color: #0F172A; font-weight: 500;
    }
    .logo-text strong { font-weight: 800; }

    .sidebar-nav {
      flex: 1; padding: 12px 12px; overflow-y: auto;
      display: flex; flex-direction: column; gap: 2px;
    }
    .nav-item {
      display: flex; align-items: center; gap: 12px;
      padding: 10px 12px; border-radius: 12px;
      text-decoration: none;
      font-family: 'DM Sans', sans-serif;
      font-size: 14px; font-weight: 500;
      color: #64748B;
      transition: background 0.15s, color 0.15s;
    }
    .nav-item:hover { background: #F8FAFC; color: #0F172A; }
    .nav-item-active { background: #F0FDF4 !important; color: #15803D !important; font-weight: 600; }
    .nav-item-active .nav-icon svg { stroke: #22C55E; }
    .nav-icon { display: flex; align-items: center; }

    .sidebar-footer {
      padding: 16px; border-top: 1px solid #F1F5F9;
      display: flex; align-items: center; gap: 10px;
    }
    .trainer-avatar-wrap {
      display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0;
    }
    .trainer-avatar-img, .trainer-avatar-initials {
      width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
    }
    .trainer-avatar-img { object-fit: cover; }
    .trainer-avatar-initials {
      background: #22C55E; color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-family: 'DM Sans', sans-serif;
      font-size: 13px; font-weight: 700;
    }
    .trainer-info { display: flex; flex-direction: column; min-width: 0; }
    .trainer-name {
      font-family: 'DM Sans', sans-serif; font-size: 13px;
      font-weight: 600; color: #0F172A;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .trainer-plan {
      font-family: 'DM Sans', sans-serif; font-size: 11px;
      color: #64748B; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .logout-btn {
      background: none; border: none; cursor: pointer;
      color: #94A3B8; padding: 6px; border-radius: 8px;
      display: flex; align-items: center; flex-shrink: 0;
      transition: background 0.15s, color 0.15s;
    }
    .logout-btn:hover { background: #FEF2F2; color: #EF4444; }

    /* Header */
    #main-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 20px 24px 0;
      margin-bottom: 8px;
    }
    .header-left { display: flex; flex-direction: column; gap: 4px; }
    .header-right { display: flex; align-items: center; gap: 12px; }
    .breadcrumb {
      display: none;
      align-items: center; gap: 4px;
    }
    @media (min-width: 1024px) { .breadcrumb { display: flex; } }
    .breadcrumb-link {
      font-family: 'DM Sans', sans-serif; font-size: 13px;
      color: #64748B; text-decoration: none;
    }
    .breadcrumb-link:hover { color: #22C55E; }
    .breadcrumb-current {
      font-family: 'DM Sans', sans-serif; font-size: 13px;
      color: #0F172A; font-weight: 500;
    }
    .page-title {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 22px; font-weight: 800;
      color: #0F172A; margin: 0;
    }
    @media (min-width: 1024px) { .page-title { font-size: 26px; } }

    /* Bottom Nav */
    #bottom-nav {
      position: fixed; bottom: 0; left: 0; right: 0;
      background: #fff; border-top: 1px solid #E2E8F0;
      display: flex; z-index: 100;
      padding-bottom: env(safe-area-inset-bottom);
    }
    @media (min-width: 1024px) { #bottom-nav { display: none; } }
    .bottom-nav-item {
      flex: 1; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      gap: 3px; padding: 8px 4px 10px;
      text-decoration: none; color: #94A3B8;
      font-family: 'DM Sans', sans-serif; font-size: 10px; font-weight: 500;
      transition: color 0.15s;
    }
    .bottom-nav-active { color: #22C55E; }
    .bottom-nav-item svg { stroke: currentColor; }

    /* Espaço para bottom nav no mobile */
    @media (max-width: 1023px) {
      #main-content { padding-bottom: 80px; }
    }
  `;
  document.head.appendChild(style);
}

function _planLabel(plan) {
  const labels = { starter: "Starter", pro: "Pro", elite: "Elite" };
  return labels[plan] || "Starter";
}

/**
 * Inicializa o layout na página.
 * Deve ser chamado após DOMContentLoaded.
 *
 * @param {string} pageTitle - Título exibido no header.
 * @param {Array<{label: string, href?: string}>} breadcrumbs - Itens do breadcrumb.
 */
function initLayout(pageTitle, breadcrumbs = []) {
  _injectLayoutStyles();

  const user = typeof Auth !== "undefined" ? Auth.getUser() : null;

  // Encontra o wrapper do conteúdo principal
  const mainContent = document.getElementById("main-content");
  if (!mainContent) {
    console.warn("[Layout] Elemento #main-content não encontrado na página.");
    return;
  }

  // Insere sidebar antes do main-content
  if (!document.getElementById("sidebar")) {
    mainContent.insertAdjacentHTML("beforebegin", _renderSidebar(user));
  }

  // Insere header dentro do main-content no início
  if (!document.getElementById("main-header")) {
    mainContent.insertAdjacentHTML("afterbegin", _renderHeader(pageTitle, breadcrumbs));
  }

  // Insere bottom nav no body
  if (!document.getElementById("bottom-nav")) {
    document.body.insertAdjacentHTML("beforeend", _renderBottomNav());
  }

  // Atualiza título da aba
  document.title = `${pageTitle} — FitFlow Pro`;

  // Revela o body depois que sidebar + fontes estão prontos (elimina auth flicker e FOUT)
  Promise.race([
    document.fonts.ready,
    new Promise((r) => setTimeout(r, 800)), // fallback: máximo 800ms de espera
  ]).then(() => {
    requestAnimationFrame(() => {
      document.body.style.opacity = "1";
    });
  });
}
