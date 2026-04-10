/**
 * modal.js — Modal reutilizável do FitFlow Pro.
 * Uso:
 *   Modal.open({
 *     title: "Confirmar exclusão",
 *     body: "<p>Tem certeza?</p>",
 *     confirmLabel: "Excluir",
 *     cancelLabel: "Cancelar",
 *     onConfirm: () => { ... },
 *     onCancel: () => { ... },
 *     dangerous: true,  // botão confirmar em vermelho
 *   });
 *   Modal.close();
 */

const Modal = (() => {
  let _overlay = null;
  let _currentOnConfirm = null;
  let _currentOnCancel = null;

  // Injeta os estilos base uma vez
  function _injectStyles() {
    if (document.getElementById("modal-styles")) return;
    const style = document.createElement("style");
    style.id = "modal-styles";
    style.textContent = `
      #modal-overlay {
        position: fixed; inset: 0; z-index: 10000;
        background: rgba(15, 23, 42, 0.5);
        backdrop-filter: blur(4px);
        display: flex; align-items: center; justify-content: center;
        padding: 16px;
        opacity: 0;
        transition: opacity 0.2s ease;
      }
      #modal-overlay.modal-visible { opacity: 1; }

      #modal-box {
        background: #fff;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.18);
        width: 100%;
        max-width: 480px;
        max-height: 90vh;
        overflow-y: auto;
        transform: translateY(16px) scale(0.98);
        transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.2s ease;
        opacity: 0;
      }
      #modal-overlay.modal-visible #modal-box {
        transform: translateY(0) scale(1);
        opacity: 1;
      }

      .modal-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 20px 24px 0;
      }
      .modal-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 18px; font-weight: 700;
        color: #0F172A; margin: 0;
      }
      .modal-close-btn {
        background: none; border: none; cursor: pointer;
        color: #64748B; padding: 4px; border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        transition: background 0.15s, color 0.15s;
      }
      .modal-close-btn:hover { background: #F1F5F9; color: #0F172A; }

      .modal-body {
        padding: 16px 24px;
        font-family: 'DM Sans', sans-serif;
        font-size: 14px; color: #475569; line-height: 1.6;
      }

      .modal-footer {
        display: flex; gap: 12px; justify-content: flex-end;
        padding: 0 24px 20px;
      }

      .modal-btn {
        font-family: 'DM Sans', sans-serif;
        font-size: 14px; font-weight: 600;
        padding: 10px 20px; border-radius: 12px;
        border: none; cursor: pointer;
        transition: opacity 0.15s, transform 0.1s;
      }
      .modal-btn:hover { opacity: 0.88; }
      .modal-btn:active { transform: scale(0.97); }

      .modal-btn-cancel {
        background: #F1F5F9; color: #475569;
      }
      .modal-btn-cancel:hover { background: #E2E8F0; }

      .modal-btn-confirm {
        background: #22C55E; color: #fff;
      }
      .modal-btn-confirm.dangerous {
        background: #EF4444;
      }
    `;
    document.head.appendChild(style);
  }

  function _buildOverlay() {
    const overlay = document.createElement("div");
    overlay.id = "modal-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");

    overlay.innerHTML = `
      <div id="modal-box">
        <div class="modal-header">
          <h2 class="modal-title" id="modal-title"></h2>
          <button class="modal-close-btn" id="modal-close-btn" aria-label="Fechar modal">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body" id="modal-body"></div>
        <div class="modal-footer" id="modal-footer"></div>
      </div>
    `;

    // Fecha ao clicar no overlay (fora do box)
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });

    // Fecha ao clicar no botão X
    overlay.querySelector("#modal-close-btn").addEventListener("click", close);

    return overlay;
  }

  /**
   * Abre o modal com as opções fornecidas.
   *
   * @param {object} options
   * @param {string} options.title - Título do modal.
   * @param {string} [options.body] - HTML do corpo.
   * @param {string} [options.confirmLabel] - Texto do botão confirmar. Padrão: "Confirmar".
   * @param {string} [options.cancelLabel] - Texto do botão cancelar. Padrão: "Cancelar". Null = oculta.
   * @param {Function} [options.onConfirm] - Callback ao confirmar.
   * @param {Function} [options.onCancel] - Callback ao cancelar.
   * @param {boolean} [options.dangerous] - Botão confirmar em vermelho.
   */
  function open(options = {}) {
    _injectStyles();

    if (_overlay) close(true); // fecha modal anterior sem animação

    _overlay = _buildOverlay();
    document.body.appendChild(_overlay);
    document.body.style.overflow = "hidden";

    // Preenche conteúdo
    _overlay.querySelector("#modal-title").textContent = options.title || "";
    _overlay.querySelector("#modal-body").innerHTML = options.body || "";

    // Monta footer
    const footer = _overlay.querySelector("#modal-footer");
    footer.innerHTML = "";

    if (options.cancelLabel !== null) {
      const cancelBtn = document.createElement("button");
      cancelBtn.className = "modal-btn modal-btn-cancel";
      cancelBtn.textContent = options.cancelLabel || "Cancelar";
      cancelBtn.addEventListener("click", () => {
        close();
        if (typeof _currentOnCancel === "function") _currentOnCancel();
      });
      footer.appendChild(cancelBtn);
    }

    const confirmBtn = document.createElement("button");
    confirmBtn.className = `modal-btn modal-btn-confirm${options.dangerous ? " dangerous" : ""}`;
    confirmBtn.textContent = options.confirmLabel || "Confirmar";
    confirmBtn.addEventListener("click", () => {
      close();
      if (typeof _currentOnConfirm === "function") _currentOnConfirm();
    });
    footer.appendChild(confirmBtn);

    _currentOnConfirm = options.onConfirm || null;
    _currentOnCancel = options.onCancel || null;

    // Animação de entrada
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        _overlay.classList.add("modal-visible");
      });
    });

    // Foco no botão confirmar para acessibilidade
    setTimeout(() => confirmBtn.focus(), 230);

    // Fecha com Esc
    document.addEventListener("keydown", _onKeyDown);
  }

  /**
   * Fecha o modal atual.
   * @param {boolean} [immediate] - Se true, remove sem animação.
   */
  function close(immediate = false) {
    if (!_overlay) return;

    document.removeEventListener("keydown", _onKeyDown);
    document.body.style.overflow = "";

    if (immediate) {
      _overlay.remove();
      _overlay = null;
      return;
    }

    _overlay.classList.remove("modal-visible");
    const el = _overlay;
    setTimeout(() => {
      el.remove();
      if (_overlay === el) _overlay = null;
    }, 220);
  }

  function _onKeyDown(e) {
    if (e.key === "Escape") close();
  }

  return { open, close };
})();
