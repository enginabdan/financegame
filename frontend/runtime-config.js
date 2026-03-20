(function () {
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const isLocal = localHosts.has(window.location.hostname);

  window.__APP_CONFIG__ = {
    API_BASE: isLocal
      ? "http://127.0.0.1:8000"
      : "https://financegame-api-919842388268.us-central1.run.app",
  };
})();
