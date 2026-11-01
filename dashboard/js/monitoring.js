/* Dashboard error reporting (Sentry), using the backend's SENTRY_DSN from /api/config.
 *
 * Reports uncaught JavaScript errors automatically, plus the dashboard problems that matter in a demo:
 * the WebSocket dropping, a command (e.g. Listen) sent while disconnected, a rejected pairing code.
 * Off in mock mode and when no DSN is set. vendor/sentry.min.js is @sentry/browser 8.55.0.
 */
(function () {
  "use strict";
  let on = false;

  function message(text, level, extra, tags) {
    if (!on) return;
    Sentry.withScope(scope => {
      scope.setTag("step", "dashboard");
      if (tags) scope.setTags(tags);
      if (extra) scope.setExtras(extra);
      Sentry.captureMessage(text, level || "warning");
    });
  }

  async function init(larp) {
    if (larp.mock || typeof Sentry === "undefined") return;
    let config = {};
    try { config = await larp.getConfig(); } catch { return; }
    if (!config.sentry_dsn) return;
    Sentry.init({ dsn: config.sentry_dsn, environment: `${config.environment || "local"}-dashboard`, tracesSampleRate: 0 });
    Sentry.setTag("app", "dashboard");
    on = true;

    let openedAt = 0;
    larp.on("open", () => { openedAt = Date.now(); });
    larp.on("close", () => message("Dashboard lost its connection to the backend", "warning",
      { connected_for_s: Math.round((Date.now() - openedAt) / 1000) }));
    larp.on("send_failed", msg => message(`Command not sent (not connected): ${msg.t}`, "warning", { command: msg }));
    larp.on("unauthorized", () => message("Dashboard rejected: wrong or missing pairing code", "info"));
  }

  window.LarpMonitor = { init, message };
})();
