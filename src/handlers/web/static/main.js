// Show loading state (spinner + elapsed-time counter) while a form submits.
//
// The loader appearance is deferred by 1 second so that fast responses
// (validation, detection, quick evaluations) don't flash a spinner at
// the user — if navigation happens within 1s the loader is never shown.
// Only slow LLM calls end up revealing the spinner + counter.
//
// Reset cleanly on bfcache restore (user hits Back from the result page):
// without this, the `setInterval` snapshot inside the cached page would
// keep ticking and the button would still look busy.
document.addEventListener("DOMContentLoaded", () => {
    const SHOW_LOADER_AFTER_MS = 1000;

    const formatElapsed = (ms) => {
        const sec = Math.floor(ms / 1000);
        const m = Math.floor(sec / 60);
        const s = String(sec % 60).padStart(2, "0");
        return `${m}:${s}`;
    };

    // Track pending teardown per button so `pageshow` (bfcache restore)
    // can cancel both the delayed show-timer and the running counter.
    const activeTimers = new Map(); // btnId -> {baseLabel, clear()}

    const resetButton = (btnId) => {
        const entry = activeTimers.get(btnId);
        if (entry) {
            entry.clear();
            activeTimers.delete(btnId);
        }
        const btn = document.getElementById(btnId);
        if (!btn) return;
        const textEl = btn.querySelector(".btn-text");
        const loadingEl = btn.querySelector(".btn-loading");
        if (textEl) textEl.classList.remove("hidden");
        if (loadingEl) {
            loadingEl.classList.add("hidden");
            if (entry) loadingEl.textContent = entry.baseLabel;
        }
        // Don't re-enable buttons that are readiness-blocked server-side
        // (aria-disabled="true" — e.g. GEMINI_API_KEY missing).
        if (btn.getAttribute("aria-disabled") !== "true") {
            btn.disabled = false;
        }
    };

    [
        ["gen-form", "gen-btn"],
        ["val-form", "val-btn"],
        ["detect-form", "detect-btn"],
        ["eval-form", "eval-btn"],
    ].forEach(([formId, btnId]) => {
        const form = document.getElementById(formId);
        if (!form) return;

        form.addEventListener("submit", () => {
            const btn = document.getElementById(btnId);
            if (!btn) return;
            const textEl = btn.querySelector(".btn-text");
            const loadingEl = btn.querySelector(".btn-loading");
            if (!textEl || !loadingEl) return;

            // Disable immediately to block double-submit, but keep the
            // original text visible until the loader-reveal timeout fires.
            btn.disabled = true;

            const baseLabel = loadingEl.textContent.trim();
            const start = Date.now();
            let intervalId = null;

            const showDelayId = window.setTimeout(() => {
                textEl.classList.add("hidden");
                loadingEl.classList.remove("hidden");
                const tick = () => {
                    loadingEl.textContent = `${baseLabel} ${formatElapsed(Date.now() - start)}`;
                };
                tick();
                intervalId = window.setInterval(tick, 1000);
            }, SHOW_LOADER_AFTER_MS);

            activeTimers.set(btnId, {
                baseLabel,
                clear: () => {
                    window.clearTimeout(showDelayId);
                    if (intervalId !== null) window.clearInterval(intervalId);
                },
            });
        });
    });

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) return;
        Array.from(activeTimers.keys()).forEach(resetButton);
    });
});
