// Show loading state while a form is submitting
document.addEventListener("DOMContentLoaded", () => {
    [["gen-form", "gen-btn"], ["detect-form", "detect-btn"]].forEach(([formId, btnId]) => {
        const form = document.getElementById(formId);
        if (!form) return;

        form.addEventListener("submit", () => {
            const btn = document.getElementById(btnId);
            if (!btn) return;
            btn.querySelector(".btn-text").classList.add("hidden");
            btn.querySelector(".btn-loading").classList.remove("hidden");
            btn.disabled = true;
        });
    });
});
