(function () {
  const API_KEY = window.__APP_CONFIG__?.FIREBASE_WEB_API_KEY || "";
  const STORAGE_KEY = "financegame_firebase_auth";
  const listeners = [];

  function loadAuth() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (_err) {
      return {};
    }
  }

  function saveAuth(payload) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload || {}));
    notify();
  }

  function clearAuth() {
    localStorage.removeItem(STORAGE_KEY);
    notify();
  }

  function getAuth() {
    return loadAuth();
  }

  function getIdToken() {
    const auth = loadAuth();
    return auth.idToken || "";
  }

  function getEmail() {
    const auth = loadAuth();
    return auth.email || "";
  }

  function notify() {
    const state = getAuth();
    listeners.forEach((cb) => {
      try {
        cb(state);
      } catch (_err) {
        // no-op
      }
    });
  }

  function onChange(cb) {
    if (typeof cb !== "function") {
      return () => {};
    }
    listeners.push(cb);
    cb(getAuth());
    return () => {
      const idx = listeners.indexOf(cb);
      if (idx >= 0) listeners.splice(idx, 1);
    };
  }

  async function firebaseAuthRequest(path, email, password) {
    if (!API_KEY) {
      throw new Error("FIREBASE_WEB_API_KEY is missing in runtime-config.js");
    }
    const res = await fetch(`https://identitytoolkit.googleapis.com/v1/${path}?key=${encodeURIComponent(API_KEY)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: (email || "").trim(),
        password: (password || "").trim(),
        returnSecureToken: true,
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const code = String(body?.error?.message || "AUTH_FAILED");
      throw new Error(code.replaceAll("_", " "));
    }
    return body;
  }

  async function signIn(email, password) {
    const body = await firebaseAuthRequest("accounts:signInWithPassword", email, password);
    saveAuth({
      email: body.email || email,
      localId: body.localId,
      idToken: body.idToken,
      refreshToken: body.refreshToken,
      expiresIn: Number(body.expiresIn || 3600),
      signedInAt: Date.now(),
    });
    return getAuth();
  }

  async function signUp(email, password) {
    const body = await firebaseAuthRequest("accounts:signUp", email, password);
    saveAuth({
      email: body.email || email,
      localId: body.localId,
      idToken: body.idToken,
      refreshToken: body.refreshToken,
      expiresIn: Number(body.expiresIn || 3600),
      signedInAt: Date.now(),
    });
    return getAuth();
  }

  async function sendPasswordReset(email) {
    if (!API_KEY) {
      throw new Error("FIREBASE_WEB_API_KEY is missing in runtime-config.js");
    }
    const cleanEmail = (email || "").trim().toLowerCase();
    if (!cleanEmail) {
      throw new Error("Email is required");
    }
    const res = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key=${encodeURIComponent(API_KEY)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        requestType: "PASSWORD_RESET",
        email: cleanEmail,
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const code = String(body?.error?.message || "PASSWORD_RESET_FAILED");
      throw new Error(code.replaceAll("_", " "));
    }
    return { email: cleanEmail, ok: true };
  }

  async function refreshIdToken() {
    const auth = loadAuth();
    if (!auth.refreshToken || !API_KEY) {
      return auth;
    }
    const ageSec = (Date.now() - Number(auth.signedInAt || 0)) / 1000;
    if (ageSec < Math.max(300, Number(auth.expiresIn || 3600) - 120)) {
      return auth;
    }
    const res = await fetch(`https://securetoken.googleapis.com/v1/token?key=${encodeURIComponent(API_KEY)}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: auth.refreshToken,
      }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      clearAuth();
      throw new Error("Session expired. Please sign in again.");
    }
    saveAuth({
      ...auth,
      idToken: body.id_token,
      refreshToken: body.refresh_token || auth.refreshToken,
      expiresIn: Number(body.expires_in || 3600),
      signedInAt: Date.now(),
    });
    return getAuth();
  }

  function signOut() {
    clearAuth();
  }

  window.FinanceAuth = {
    getAuth,
    getIdToken,
    getEmail,
    signIn,
    signUp,
    sendPasswordReset,
    signOut,
    onChange,
    refreshIdToken,
  };
})();
