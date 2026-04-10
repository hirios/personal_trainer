/**
 * auth.js — Gerenciamento de sessão do FitFlow Pro.
 * Centraliza login, logout, verificação de autenticação e dados do usuário.
 * Depende de api.js (deve ser carregado antes).
 */

const Auth = (() => {
  const USER_KEY = "fitflow_user";
  const ACCESS_KEY = "access_token";
  const REFRESH_KEY = "refresh_token";

  // Rotas de redirecionamento por papel
  const REDIRECT_AFTER_LOGIN = {
    trainer: "/frontend/trainer/index.html",
    student: "/frontend/student/index.html",
    default: "/frontend/public/login.html",
  };
  const LOGIN_PAGE = "/frontend/public/login.html";

  /**
   * Tenta autenticar o usuário com email e senha.
   * Em caso de sucesso, salva os tokens e redireciona.
   *
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{success: boolean, message: string}>}
   */
  async function login(email, password) {
    const result = await Api.post("/api/auth/login", { email, password });

    if (result.success && result.data) {
      _saveSession(result.data);
      const role = result.data.user?.role || "default";
      window.location.href = REDIRECT_AFTER_LOGIN[role] || REDIRECT_AFTER_LOGIN.default;
      return { success: true, message: result.message };
    }

    return { success: false, message: result.message || "Erro ao fazer login." };
  }

  /**
   * Encerra a sessão: remove tokens locais e invalida o refresh_token no backend.
   */
  async function logout() {
    const refreshToken = sessionStorage.getItem(REFRESH_KEY);

    // Tenta invalidar o token no backend (best-effort, não bloqueia o logout local)
    if (refreshToken) {
      try {
        await fetch(`${window.API_BASE_URL || window.location.origin}/api/auth/logout`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${refreshToken}`,
          },
        });
      } catch {
        // Ignora erros de rede no logout — a sessão local será limpa de qualquer forma
      }
    }

    _clearSession();
    window.location.href = LOGIN_PAGE;
  }

  /**
   * Verifica se existe um access_token na sessão.
   * Nota: não valida a assinatura JWT (isso é responsabilidade do servidor).
   *
   * @returns {boolean}
   */
  function isLoggedIn() {
    return !!sessionStorage.getItem(ACCESS_KEY);
  }

  /**
   * Retorna os dados do usuário armazenados na sessão.
   *
   * @returns {object|null}
   */
  function getUser() {
    const raw = sessionStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  /**
   * Atualiza os dados do usuário no storage (após edição de perfil, por exemplo).
   *
   * @param {object} userData
   */
  function updateUser(userData) {
    sessionStorage.setItem(USER_KEY, JSON.stringify(userData));
  }

  /**
   * Guarda proteção em páginas autenticadas.
   * Chame no topo de cada página protegida.
   * Se não autenticado, redireciona para login.
   *
   * @param {'trainer'|'student'|null} requiredRole - Papel necessário (opcional).
   */
  function requireAuth(requiredRole = null) {
    if (!isLoggedIn()) {
      window.location.href = LOGIN_PAGE;
      return;
    }

    if (requiredRole) {
      const user = getUser();
      if (user?.role !== requiredRole) {
        // Redireciona para a área correta do usuário logado
        const redirect = REDIRECT_AFTER_LOGIN[user?.role] || LOGIN_PAGE;
        window.location.href = redirect;
      }
    }
  }

  // --- Helpers privados ---

  function _saveSession(data) {
    sessionStorage.setItem(ACCESS_KEY, data.access_token);
    sessionStorage.setItem(REFRESH_KEY, data.refresh_token);
    sessionStorage.setItem(USER_KEY, JSON.stringify(data.user));
    // Expõe tokens para o módulo Api.js via o próprio sessionStorage
    Api._saveTokens(data.access_token, data.refresh_token);
  }

  function _clearSession() {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
    sessionStorage.removeItem(USER_KEY);
  }

  return { login, logout, isLoggedIn, getUser, updateUser, requireAuth };
})();
