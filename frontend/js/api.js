/**
 * api.js — Módulo central de chamadas HTTP do FitFlow Pro.
 * Gerencia autenticação, refresh automático de token e erros de rede.
 * Expõe o objeto global `Api` com métodos get, post, patch, del.
 */

const Api = (() => {
  // URL base da API — ajuste conforme o ambiente
  const BASE_URL = window.API_BASE_URL || "http://localhost:5000";

  // Flag para evitar múltiplos refreshes simultâneos
  let _refreshing = false;
  let _refreshQueue = [];

  /**
   * Retorna o access token armazenado na sessão.
   */
  function _getAccessToken() {
    return sessionStorage.getItem("access_token");
  }

  /**
   * Retorna o refresh token armazenado na sessão.
   */
  function _getRefreshToken() {
    return sessionStorage.getItem("refresh_token");
  }

  /**
   * Salva os tokens na sessionStorage.
   */
  function _saveTokens(accessToken, refreshToken) {
    sessionStorage.setItem("access_token", accessToken);
    if (refreshToken) {
      sessionStorage.setItem("refresh_token", refreshToken);
    }
  }

  /**
   * Tenta renovar o access_token usando o refresh_token.
   * Se falhar, redireciona para o login.
   * @returns {Promise<string|null>} Novo access token ou null se falhar.
   */
  async function _doRefresh() {
    const refreshToken = _getRefreshToken();
    if (!refreshToken) {
      Auth.logout();
      return null;
    }

    try {
      const response = await fetch(`${BASE_URL}/api/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${refreshToken}`,
        },
      });

      if (!response.ok) {
        Auth.logout();
        return null;
      }

      const result = await response.json();
      if (result.success && result.data?.access_token) {
        _saveTokens(result.data.access_token, null);
        return result.data.access_token;
      }

      Auth.logout();
      return null;
    } catch {
      Auth.logout();
      return null;
    }
  }

  /**
   * Garante que apenas um refresh ocorra por vez.
   * Outros chamadores ficam na fila e recebem o mesmo token.
   */
  async function _refreshToken() {
    if (_refreshing) {
      return new Promise((resolve) => _refreshQueue.push(resolve));
    }

    _refreshing = true;
    const token = await _doRefresh();
    _refreshing = false;

    // Resolve todos que estavam na fila com o mesmo novo token
    _refreshQueue.forEach((resolve) => resolve(token));
    _refreshQueue = [];

    return token;
  }

  /**
   * Realiza uma requisição HTTP autenticada.
   * Em caso de 401, tenta refresh e repete a requisição uma vez.
   *
   * @param {string} method - Método HTTP.
   * @param {string} path - Caminho relativo (ex: /api/auth/me).
   * @param {object|null} body - Corpo da requisição (JSON).
   * @param {object} params - Query params (objeto chave-valor).
   * @returns {Promise<object>} Resposta JSON da API.
   */
  async function _request(method, path, body = null, params = {}) {
    // Monta query string
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null)
    ).toString();
    const url = `${BASE_URL}${path}${qs ? "?" + qs : ""}`;

    const buildHeaders = (token) => {
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      return headers;
    };

    const buildOptions = (token) => ({
      method,
      headers: buildHeaders(token),
      body: body ? JSON.stringify(body) : undefined,
    });

    let accessToken = _getAccessToken();
    let response = await fetch(url, buildOptions(accessToken));

    // Tenta refresh se receber 401
    if (response.status === 401) {
      const newToken = await _refreshToken();
      if (!newToken) return { success: false, data: null, message: "Sessão expirada." };

      // Repete a requisição com o novo token
      response = await fetch(url, buildOptions(newToken));
    }

    // Erros de rede (sem resposta JSON)
    if (!response.ok && response.status >= 500) {
      return {
        success: false,
        data: null,
        message: "Erro no servidor. Tente novamente em breve.",
      };
    }

    try {
      return await response.json();
    } catch {
      return { success: false, data: null, message: "Resposta inválida do servidor." };
    }
  }

  // --- API Pública ---

  /**
   * GET /path?params
   */
  async function get(path, params = {}) {
    return _request("GET", path, null, params);
  }

  /**
   * POST /path com body JSON
   */
  async function post(path, body = {}) {
    return _request("POST", path, body);
  }

  /**
   * PATCH /path com body JSON
   */
  async function patch(path, body = {}) {
    return _request("PATCH", path, body);
  }

  /**
   * DELETE /path
   */
  async function del(path) {
    return _request("DELETE", path);
  }

  /**
   * PUT /path com body JSON
   */
  async function put(path, body = {}) {
    return _request("PUT", path, body);
  }

  return { get, post, patch, put, del, _saveTokens };
})();
