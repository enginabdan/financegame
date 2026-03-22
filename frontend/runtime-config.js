(function () {
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const isLocal = localHosts.has(window.location.hostname);

  window.__APP_CONFIG__ = {
    API_BASE: isLocal
      ? "http://127.0.0.1:8000"
      : "https://api.bosembo.net",
    FIREBASE_WEB_API_KEY: "AIzaSyDjsUtglMdBGcsOz4EDUUd6_LTQ9jMzj_c",
  };
})();
