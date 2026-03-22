(function () {
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const isLocal = localHosts.has(window.location.hostname);

  window.__APP_CONFIG__ = {
    API_BASE: isLocal
      ? "http://127.0.0.1:8000"
      : "https://financegame-api-919842388268.us-central1.run.app",
    FIREBASE_WEB_API_KEY: "AIzaSyDjsUtglMdBGcsOz4EDUUd6_LTQ9jMzj_c",
    TEACHER_KEY: "tmsacharlottesecondaryschoolteacherkey",
    STUDENT_SIGNUP_KEY: "tmsacharlottesecondaryschoolstudentkey",
  };
})();
