// Show loading state (spinner + elapsed-time counter) while a form submits.
//
// Two modes:
//   * FAST forms (validation, detection) — native submit. Spinner reveal
//     is deferred by 1 s so quick responses don't flash it.
//   * SLOW forms (generation, ablation) — intercept submit, POST via
//     fetch() with an AbortController. This lets the user press
//     "Скасувати" mid-flight and also shows a "taking longer than
//     expected" warning once the call crosses LONG_WAIT_WARN_MS.
//
// Reset cleanly on bfcache restore (user hits Back from the result page):
// without this, the `setInterval` snapshot inside the cached page would
// keep ticking and the button would still look busy.
document.addEventListener("DOMContentLoaded", () => {
    enhanceSelects();

    const FAST_SHOW_AFTER_MS = 1000;
    const SLOW_SHOW_AFTER_MS = 0;
    // Matches the "up to 2 minutes" expectation shown in the form hints
    // (generate.html, evaluate.html). Once the call crosses this mark the
    // user has waited longer than promised, so we surface the warning.
    const LONG_WAIT_WARN_MS = 120_000;

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

    // Spinner + timer bookkeeping shared by fast and slow form handlers.
    const startSpinner = (btn, showAfterMs) => {
        const textEl = btn.querySelector(".btn-text");
        const loadingEl = btn.querySelector(".btn-loading");
        if (!textEl || !loadingEl) return null;

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
        }, showAfterMs);

        return {
            baseLabel,
            clear: () => {
                window.clearTimeout(showDelayId);
                if (intervalId !== null) window.clearInterval(intervalId);
            },
        };
    };

    // Slow forms: submit via fetch, support Cancel, surface long-wait warning.
    const wireSlowForm = ({formId, btnId, cancelBtnId, warningId}) => {
        const form = document.getElementById(formId);
        if (!form) return;
        const btn = document.getElementById(btnId);
        const cancelBtn = document.getElementById(cancelBtnId);
        const warning = document.getElementById(warningId);

        form.addEventListener("submit", async (e) => {
            // Native submit would replace the page mid-flight and kill
            // our AbortController — intercept and drive the POST ourselves.
            e.preventDefault();
            if (btn && btn.getAttribute("aria-disabled") === "true") return;

            const timerEntry = startSpinner(btn, SLOW_SHOW_AFTER_MS);
            const controller = new AbortController();
            let warnTimerId = null;

            const teardown = () => {
                if (warnTimerId !== null) window.clearTimeout(warnTimerId);
                if (warning) warning.classList.add("hidden");
                if (cancelBtn) cancelBtn.classList.add("hidden");
                resetButton(btnId);
            };

            if (cancelBtn) {
                cancelBtn.classList.remove("hidden");
                // One-shot listener: remove on teardown so a second run
                // starts from a clean slate.
                const onCancel = () => {
                    controller.abort();
                    cancelBtn.removeEventListener("click", onCancel);
                };
                cancelBtn.addEventListener("click", onCancel);
            }
            if (warning) {
                warnTimerId = window.setTimeout(() => {
                    warning.classList.remove("hidden");
                }, LONG_WAIT_WARN_MS);
            }

            activeTimers.set(btnId, {
                baseLabel: timerEntry ? timerEntry.baseLabel : "",
                clear: () => {
                    if (timerEntry) timerEntry.clear();
                    if (warnTimerId !== null) window.clearTimeout(warnTimerId);
                },
            });

            try {
                const res = await fetch(form.action || window.location.href, {
                    method: form.method || "POST",
                    body: new FormData(form),
                    signal: controller.signal,
                    redirect: "follow",
                });
                const html = await res.text();
                // Replace the full document with the server response so
                // result.html / error.html render exactly as they would
                // after a native form submit.
                document.open();
                document.write(html);
                document.close();
            } catch (err) {
                teardown();
                if (err && err.name === "AbortError") return;
                // Unexpected transport failure (network down, CORS, etc).
                // Don't invent a fake error page — just surface it on the
                // warning banner so the user isn't left in the dark.
                if (warning) {
                    warning.textContent =
                        "Помилка мережі: " + (err && err.message ? err.message : "невідома помилка");
                    warning.classList.remove("hidden");
                }
            }
        });

        window.addEventListener("pageshow", (event) => {
            if (!event.persisted) return;
            if (warning) warning.classList.add("hidden");
            if (cancelBtn) cancelBtn.classList.add("hidden");
        });
    };

    // Fast forms keep the original native-submit + deferred-spinner path.
    const wireFastForm = (formId, btnId) => {
        const form = document.getElementById(formId);
        if (!form) return;
        form.addEventListener("submit", () => {
            const btn = document.getElementById(btnId);
            if (!btn) return;
            const entry = startSpinner(btn, FAST_SHOW_AFTER_MS);
            if (entry) activeTimers.set(btnId, entry);
        });
    };

    wireSlowForm({
        formId: "gen-form",
        btnId: "gen-btn",
        cancelBtnId: "gen-cancel",
        warningId: "gen-warning",
    });
    wireSlowForm({
        formId: "eval-form",
        btnId: "eval-btn",
        cancelBtnId: "eval-cancel",
        warningId: "eval-warning",
    });
    wireFastForm("val-form", "val-btn");
    wireFastForm("detect-form", "detect-btn");

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) return;
        Array.from(activeTimers.keys()).forEach(resetButton);
    });
});

// Replace every single-value <select> with a custom dropdown. The native
// element is kept in the DOM (visually hidden, aria-hidden) so form
// submission still carries its value — the custom UI only mirrors state.
// Native popups can't be styled cross-browser, hence the custom rendering.
function enhanceSelects() {
    const selects = document.querySelectorAll(
        "select:not([multiple]):not([data-enhanced])"
    );
    selects.forEach(enhanceSelect);

    // Close any open dropdown on outside click / Escape.
    document.addEventListener("click", (e) => {
        document.querySelectorAll(".custom-select.is-open").forEach((w) => {
            if (!w.contains(e.target)) closeCustomSelect(w);
        });
    });
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        document.querySelectorAll(".custom-select.is-open").forEach((w) => {
            closeCustomSelect(w);
            w.querySelector(".custom-select__trigger")?.focus();
        });
    });

    // Reposition any open panel when the layout shifts — keeps it clamped
    // to the viewport and flipped correctly as the trigger moves.
    const reposition = () => {
        document
            .querySelectorAll(".custom-select.is-open")
            .forEach(positionCustomSelectPanel);
    };
    window.addEventListener("resize", reposition);
    window.addEventListener("scroll", reposition, true);
}

function enhanceSelect(selectEl) {
    if (selectEl.dataset.enhanced === "true") return;
    selectEl.dataset.enhanced = "true";

    const wrapper = document.createElement("div");
    wrapper.className = "custom-select";

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "custom-select__trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    if (selectEl.disabled) trigger.disabled = true;

    const label = selectEl.id
        ? document.querySelector(`label[for="${CSS.escape(selectEl.id)}"]`)
        : null;
    if (label) {
        if (!label.id) label.id = `${selectEl.id}-label`;
        trigger.setAttribute("aria-labelledby", label.id);
        // Clicking the label should open the custom dropdown, not silently
        // focus the hidden native select.
        label.addEventListener("click", (e) => {
            e.preventDefault();
            trigger.focus();
            toggleCustomSelect(wrapper);
        });
    }

    const valueEl = document.createElement("span");
    valueEl.className = "custom-select__value";
    trigger.appendChild(valueEl);

    const chevron = document.createElement("span");
    chevron.className = "custom-select__chevron";
    chevron.setAttribute("aria-hidden", "true");
    trigger.appendChild(chevron);

    const panel = document.createElement("ul");
    panel.className = "custom-select__panel";
    panel.setAttribute("role", "listbox");
    panel.hidden = true;

    Array.from(selectEl.options).forEach((opt) => {
        const item = document.createElement("li");
        item.className = "custom-select__option";
        item.setAttribute("role", "option");
        item.dataset.value = opt.value;
        item.textContent = opt.textContent;
        item.tabIndex = -1;
        if (opt.disabled) {
            item.classList.add("is-disabled");
            item.setAttribute("aria-disabled", "true");
        }
        item.addEventListener("click", () => {
            if (opt.disabled) return;
            selectNativeValue(selectEl, opt.value);
            closeCustomSelect(wrapper);
            trigger.focus();
        });
        item.addEventListener("mouseenter", () => {
            panel
                .querySelectorAll(".is-active")
                .forEach((n) => n.classList.remove("is-active"));
            item.classList.add("is-active");
        });
        panel.appendChild(item);
    });

    selectEl.parentNode.insertBefore(wrapper, selectEl);
    wrapper.appendChild(trigger);
    wrapper.appendChild(panel);
    wrapper.appendChild(selectEl);
    selectEl.classList.add("custom-select__native");
    selectEl.setAttribute("aria-hidden", "true");
    selectEl.tabIndex = -1;

    syncCustomSelect(wrapper, selectEl);

    trigger.addEventListener("click", (e) => {
        e.preventDefault();
        toggleCustomSelect(wrapper);
    });
    trigger.addEventListener("keydown", (e) => {
        if (["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) {
            e.preventDefault();
            openCustomSelect(wrapper);
        }
    });
    panel.addEventListener("keydown", (e) => handlePanelKey(e, wrapper, selectEl));

    selectEl.addEventListener("change", () => syncCustomSelect(wrapper, selectEl));
}

function selectNativeValue(selectEl, value) {
    if (selectEl.value === value) {
        // Still dispatch so dependent UI (mirroring) stays in sync, but
        // skip if genuinely identical to avoid redundant events.
        return;
    }
    selectEl.value = value;
    selectEl.dispatchEvent(new Event("input", { bubbles: true }));
    selectEl.dispatchEvent(new Event("change", { bubbles: true }));
}

function syncCustomSelect(wrapper, selectEl) {
    const selectedOpt = selectEl.options[selectEl.selectedIndex];
    const valueEl = wrapper.querySelector(".custom-select__value");
    if (valueEl) {
        valueEl.textContent = selectedOpt ? selectedOpt.textContent : "";
    }
    wrapper.querySelectorAll(".custom-select__option").forEach((item) => {
        const match = selectedOpt && item.dataset.value === selectedOpt.value;
        item.classList.toggle("is-selected", match);
        item.setAttribute("aria-selected", match ? "true" : "false");
    });
}

function openCustomSelect(wrapper) {
    if (wrapper.classList.contains("is-open")) return;
    // Close siblings.
    document.querySelectorAll(".custom-select.is-open").forEach((w) => {
        if (w !== wrapper) closeCustomSelect(w);
    });
    const panel = wrapper.querySelector(".custom-select__panel");
    const trigger = wrapper.querySelector(".custom-select__trigger");
    panel.hidden = false;
    wrapper.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");

    positionCustomSelectPanel(wrapper);

    const selected =
        panel.querySelector(".custom-select__option.is-selected") ||
        panel.querySelector(".custom-select__option:not(.is-disabled)");
    if (selected) {
        panel
            .querySelectorAll(".is-active")
            .forEach((n) => n.classList.remove("is-active"));
        selected.classList.add("is-active");
        selected.focus({ preventScroll: true });
        selected.scrollIntoView({ block: "nearest" });
    }
}

// Clamp the open panel to available viewport space. If there's more room
// above the trigger than below, flip it up; otherwise sit beneath. The
// panel's own overflow-y:auto handles the scrollbar once max-height is set.
function positionCustomSelectPanel(wrapper) {
    const panel = wrapper.querySelector(".custom-select__panel");
    const trigger = wrapper.querySelector(".custom-select__trigger");
    if (!panel || !trigger) return;

    const MIN_PANEL = 120; // never shrink below this — always scrollable
    const GAP = 4;
    const VIEWPORT_MARGIN = 8;

    const rect = trigger.getBoundingClientRect();
    const viewportH = window.innerHeight;
    const spaceBelow = viewportH - rect.bottom - GAP - VIEWPORT_MARGIN;
    const spaceAbove = rect.top - GAP - VIEWPORT_MARGIN;

    const flipUp = spaceBelow < MIN_PANEL && spaceAbove > spaceBelow;
    wrapper.classList.toggle("custom-select--flip-up", flipUp);
    const available = Math.max(MIN_PANEL, flipUp ? spaceAbove : spaceBelow);
    panel.style.maxHeight = `${Math.floor(available)}px`;
}

function closeCustomSelect(wrapper) {
    const panel = wrapper.querySelector(".custom-select__panel");
    const trigger = wrapper.querySelector(".custom-select__trigger");
    panel.hidden = true;
    wrapper.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
    panel
        .querySelectorAll(".is-active")
        .forEach((n) => n.classList.remove("is-active"));
}

function toggleCustomSelect(wrapper) {
    if (wrapper.classList.contains("is-open")) closeCustomSelect(wrapper);
    else openCustomSelect(wrapper);
}

function handlePanelKey(e, wrapper, selectEl) {
    const panel = wrapper.querySelector(".custom-select__panel");
    const trigger = wrapper.querySelector(".custom-select__trigger");
    const items = Array.from(
        panel.querySelectorAll(".custom-select__option:not(.is-disabled)")
    );
    if (!items.length) return;
    const active = document.activeElement;
    let idx = items.indexOf(active);

    switch (e.key) {
        case "ArrowDown":
            e.preventDefault();
            idx = Math.min(items.length - 1, idx + 1);
            focusItem(items[idx]);
            break;
        case "ArrowUp":
            e.preventDefault();
            idx = Math.max(0, idx - 1);
            focusItem(items[idx]);
            break;
        case "Home":
            e.preventDefault();
            focusItem(items[0]);
            break;
        case "End":
            e.preventDefault();
            focusItem(items[items.length - 1]);
            break;
        case "Enter":
        case " ":
            e.preventDefault();
            if (active && active.classList.contains("custom-select__option")) {
                selectNativeValue(selectEl, active.dataset.value);
            }
            closeCustomSelect(wrapper);
            trigger.focus();
            break;
        case "Tab":
            closeCustomSelect(wrapper);
            break;
    }
}

function focusItem(item) {
    if (!item) return;
    const panel = item.parentElement;
    panel
        .querySelectorAll(".is-active")
        .forEach((n) => n.classList.remove("is-active"));
    item.classList.add("is-active");
    item.focus({ preventScroll: true });
    item.scrollIntoView({ block: "nearest" });
}
