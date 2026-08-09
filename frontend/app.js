/**
 * Departures — frontend for the Travel Planning Agent API.
 *
 * Vanilla JS, no build step. Talks to the FastAPI backend's
 * /api/v1 endpoints: /health, /trip/plan, /trip/followup,
 * /trip/session/{id}.
 */
(() => {
  "use strict";

  const DEFAULT_API_BASE = "http://localhost:8000/api/v1";
  const STORAGE_KEYS = {
    apiBase: "tp_api_base",
    sessionId: "tp_session_id",
    destination: "tp_destination",
  };

  const INTERESTS = [
    "culture", "history", "food", "nature", "adventure", "nightlife",
    "relaxation", "shopping", "art", "family", "beaches", "photography",
  ];

  const FLIP_DESTINATIONS = [
    "Kyoto?", "Lisbon?", "Oaxaca?", "Reykjavík?", "Marrakesh?", "Queenstown?",
  ];

  // ---------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------
  const state = {
    apiBase: localStorage.getItem(STORAGE_KEYS.apiBase) || DEFAULT_API_BASE,
    sessionId: localStorage.getItem(STORAGE_KEYS.sessionId) || null,
    destination: localStorage.getItem(STORAGE_KEYS.destination) || null,
    selectedInterests: new Set(),
  };

  // ---------------------------------------------------------------------
  // DOM refs
  // ---------------------------------------------------------------------
  const el = {
    statusDot: document.getElementById("status-dot"),
    statusText: document.getElementById("status-text"),
    apiConfigBtn: document.getElementById("api-config-btn"),
    apiPopover: document.getElementById("api-popover"),
    apiBaseInput: document.getElementById("api-base-input"),
    apiCancelBtn: document.getElementById("api-cancel-btn"),
    apiSaveBtn: document.getElementById("api-save-btn"),

    flipDestination: document.getElementById("flip-destination"),
    passCode: document.getElementById("pass-code"),

    form: document.getElementById("trip-form"),
    formError: document.getElementById("form-error"),
    formErrorText: document.getElementById("form-error-text"),
    submitBtn: document.getElementById("submit-btn"),
    newTripBtn: document.getElementById("new-trip-btn"),
    formHint: document.getElementById("form-hint"),
    interestChips: document.getElementById("interest-chips"),

    results: document.getElementById("results"),
    stubDestination: document.getElementById("stub-destination"),
    stubDuration: document.getElementById("stub-duration"),
    stubTravelers: document.getElementById("stub-travelers"),
    stubSession: document.getElementById("stub-session"),
    toolsUsed: document.getElementById("tools-used"),
    itineraryContent: document.getElementById("itinerary-content"),

    tower: document.getElementById("tower"),
    chatError: document.getElementById("chat-error"),
    chatErrorText: document.getElementById("chat-error-text"),
    log: document.getElementById("log"),
    followupForm: document.getElementById("followup-form"),
    followupInput: document.getElementById("followup-input"),
    followupBtn: document.getElementById("followup-btn"),
  };

  // ---------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------
  function renderMarkdown(text) {
    if (!text) return "";
    const raw = window.marked ? window.marked.parse(text) : text;
    return window.DOMPurify ? window.DOMPurify.sanitize(raw) : raw;
  }

  function fmtDate(d) {
    const [y, m, day] = d.split("-");
    return `${y}-${m}-${day}`;
  }

  function showBanner(bannerEl, textEl, message) {
    textEl.textContent = message;
    bannerEl.classList.add("show");
  }

  function hideBanner(bannerEl) {
    bannerEl.classList.remove("show");
  }

  /** Normalizes FastAPI error bodies (422 validation arrays, or plain detail strings). */
  function extractErrorMessage(status, body) {
    if (!body) return `Request failed (HTTP ${status}).`;
    const detail = body.detail;
    if (Array.isArray(detail)) {
      return detail
        .map((e) => {
          const loc = Array.isArray(e.loc) ? e.loc.filter((p) => p !== "body").join(".") : "";
          return loc ? `${loc}: ${e.msg}` : e.msg;
        })
        .join(" · ");
    }
    if (typeof detail === "string") return detail;
    return `Request failed (HTTP ${status}).`;
  }

  async function apiFetch(path, options = {}) {
    const url = `${state.apiBase}${path}`;
    let resp;
    try {
      resp = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
    } catch (networkErr) {
      const err = new Error(
        `Can't reach the API at ${state.apiBase}. Is the backend running? (${networkErr.message})`
      );
      err.isNetworkError = true;
      throw err;
    }

    let body = null;
    const text = await resp.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = null;
      }
    }

    if (!resp.ok) {
      const err = new Error(extractErrorMessage(resp.status, body));
      err.status = resp.status;
      err.body = body;
      throw err;
    }

    return body;
  }

  // ---------------------------------------------------------------------
  // Health check
  // ---------------------------------------------------------------------
  async function checkHealth() {
    el.statusDot.dataset.state = "unknown";
    el.statusText.textContent = "checking…";
    try {
      const health = await apiFetch("/health");
      if (health.status === "ok" && health.llm_configured) {
        el.statusDot.dataset.state = "ok";
        el.statusText.textContent = `online · ${health.llm_provider}`;
      } else if (health.status === "ok" && !health.llm_configured) {
        el.statusDot.dataset.state = "warn";
        el.statusText.textContent = "online · LLM key missing on server";
      } else {
        el.statusDot.dataset.state = "warn";
        el.statusText.textContent = "degraded";
      }
    } catch (err) {
      el.statusDot.dataset.state = "down";
      el.statusText.textContent = "unreachable";
    }
  }

  // ---------------------------------------------------------------------
  // API settings popover
  // ---------------------------------------------------------------------
  function openApiPopover() {
    el.apiBaseInput.value = state.apiBase;
    el.apiPopover.classList.add("show");
    el.apiBaseInput.focus();
  }

  function closeApiPopover() {
    el.apiPopover.classList.remove("show");
  }

  el.apiConfigBtn.addEventListener("click", () => {
    el.apiPopover.classList.contains("show") ? closeApiPopover() : openApiPopover();
  });
  el.apiCancelBtn.addEventListener("click", closeApiPopover);
  el.apiSaveBtn.addEventListener("click", () => {
    const value = el.apiBaseInput.value.trim().replace(/\/+$/, "");
    if (value) {
      state.apiBase = value;
      localStorage.setItem(STORAGE_KEYS.apiBase, value);
    }
    closeApiPopover();
    checkHealth();
  });
  document.addEventListener("click", (e) => {
    if (!el.apiPopover.contains(e.target) && e.target !== el.apiConfigBtn) {
      closeApiPopover();
    }
  });

  // ---------------------------------------------------------------------
  // Hero flip-text
  // ---------------------------------------------------------------------
  function startFlipText() {
    let i = 0;
    setInterval(() => {
      i = (i + 1) % FLIP_DESTINATIONS.length;
      el.flipDestination.textContent = FLIP_DESTINATIONS[i];
    }, 2600);
  }

  // ---------------------------------------------------------------------
  // Interest chips
  // ---------------------------------------------------------------------
  function buildInterestChips() {
    el.interestChips.innerHTML = "";
    for (const interest of INTERESTS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip";
      btn.textContent = interest.replace("_", " ");
      btn.setAttribute("aria-pressed", "false");
      btn.addEventListener("click", () => {
        const pressed = btn.getAttribute("aria-pressed") === "true";
        btn.setAttribute("aria-pressed", String(!pressed));
        if (pressed) state.selectedInterests.delete(interest);
        else state.selectedInterests.add(interest);
      });
      el.interestChips.appendChild(btn);
    }
  }

  // ---------------------------------------------------------------------
  // Form defaults
  // ---------------------------------------------------------------------
  function setDefaultDates() {
    const start = new Date();
    start.setDate(start.getDate() + 30);
    const end = new Date(start);
    end.setDate(end.getDate() + 7);
    const iso = (d) => d.toISOString().slice(0, 10);
    document.getElementById("start_date").value = iso(start);
    document.getElementById("end_date").value = iso(end);
  }

  // ---------------------------------------------------------------------
  // Plan trip
  // ---------------------------------------------------------------------
  function setLoading(isLoading, label) {
    el.submitBtn.disabled = isLoading;
    if (isLoading) {
      el.submitBtn.classList.add("boarding");
      el.submitBtn.textContent = label;
    } else {
      el.submitBtn.classList.remove("boarding");
      el.submitBtn.textContent = "Plan the trip";
    }
  }

  function buildTripPayload() {
    const destination = document.getElementById("destination").value.trim();
    const startDate = document.getElementById("start_date").value;
    const endDate = document.getElementById("end_date").value;
    const originCity = document.getElementById("origin_city").value.trim();
    const travelers = parseInt(document.getElementById("travelers").value, 10);
    const budgetAmount = parseFloat(document.getElementById("budget_amount").value);
    const budgetCurrency = document.getElementById("budget_currency").value.trim().toUpperCase() || "USD";
    const budgetLevel = document.getElementById("budget_level").value;
    const notes = document.getElementById("notes").value.trim();

    const payload = {
      destination,
      start_date: startDate,
      end_date: endDate,
      travelers,
      budget_amount: budgetAmount,
      budget_currency: budgetCurrency,
      budget_level: budgetLevel,
      interests: Array.from(state.selectedInterests),
    };
    if (originCity) payload.origin_city = originCity;
    if (notes) payload.additional_notes = notes;
    return payload;
  }

  async function handlePlanSubmit(e) {
    e.preventDefault();
    hideBanner(el.formError);

    const payload = buildTripPayload();
    setLoading(true, "Boarding");

    try {
      const result = await apiFetch("/trip/plan", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      state.sessionId = result.session_id;
      state.destination = result.destination;
      localStorage.setItem(STORAGE_KEYS.sessionId, result.session_id);
      localStorage.setItem(STORAGE_KEYS.destination, result.destination);

      renderTicket(result);
      clearLog();
      el.tower.classList.add("show");
      el.newTripBtn.style.display = "inline-block";
      el.results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showBanner(el.formError, el.formErrorText, err.message);
    } finally {
      setLoading(false);
    }
  }

  function renderTicket(result) {
    el.stubDestination.textContent = result.destination;
    el.stubDuration.textContent = `${result.duration_days} day${result.duration_days === 1 ? "" : "s"}`;
    el.stubTravelers.textContent = document.getElementById("travelers").value;
    el.stubSession.textContent = result.session_id.slice(0, 8).toUpperCase();
    el.passCode.textContent = `PNR · ${result.session_id.slice(0, 8).toUpperCase()}`;

    el.toolsUsed.innerHTML = "";
    (result.tools_used || []).forEach((tool) => {
      const pill = document.createElement("span");
      pill.className = "stamp-pill";
      pill.textContent = tool.replace(/_/g, " ");
      el.toolsUsed.appendChild(pill);
    });

    el.itineraryContent.innerHTML = renderMarkdown(result.itinerary);
    el.results.classList.add("show");
  }

  // ---------------------------------------------------------------------
  // Follow-up chat ("control tower")
  // ---------------------------------------------------------------------
  function clearLog() {
    el.log.innerHTML = '<div class="log-empty">No transmissions yet. Ask about restaurants, swap a day, adjust the budget…</div>';
  }

  function appendMessage(role, content) {
    const empty = el.log.querySelector(".log-empty");
    if (empty) empty.remove();

    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;

    const meta = document.createElement("div");
    meta.className = "meta";
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    meta.textContent = role === "user" ? `You · ${time}` : `Agent · ${time}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "user") {
      bubble.textContent = content; // plain text, auto-escaped
    } else {
      bubble.innerHTML = renderMarkdown(content);
    }

    wrap.appendChild(meta);
    wrap.appendChild(bubble);
    el.log.appendChild(wrap);
    el.log.scrollTop = el.log.scrollHeight;
  }

  function setFollowupLoading(isLoading) {
    el.followupBtn.disabled = isLoading;
    el.followupInput.disabled = isLoading;
    el.followupBtn.classList.toggle("boarding", isLoading);
    el.followupBtn.textContent = isLoading ? "Sending" : "Send";
  }

  async function handleFollowupSubmit(e) {
    e.preventDefault();
    hideBanner(el.chatError);

    const question = el.followupInput.value.trim();
    if (!question || !state.sessionId) return;

    appendMessage("user", question);
    el.followupInput.value = "";
    setFollowupLoading(true);

    try {
      const result = await apiFetch("/trip/followup", {
        method: "POST",
        body: JSON.stringify({ session_id: state.sessionId, question }),
      });
      appendMessage("agent", result.answer);
    } catch (err) {
      if (err.status === 404) {
        showBanner(
          el.chatError,
          el.chatErrorText,
          "This session has expired. Start a new trip to keep chatting."
        );
        resetSession();
      } else {
        showBanner(el.chatError, el.chatErrorText, err.message);
      }
    } finally {
      setFollowupLoading(false);
    }
  }

  // ---------------------------------------------------------------------
  // Session lifecycle
  // ---------------------------------------------------------------------
  function resetSession() {
    state.sessionId = null;
    state.destination = null;
    localStorage.removeItem(STORAGE_KEYS.sessionId);
    localStorage.removeItem(STORAGE_KEYS.destination);
  }

  function startNewTrip() {
    resetSession();
    el.results.classList.remove("show");
    el.tower.classList.remove("show");
    el.newTripBtn.style.display = "none";
    el.passCode.textContent = "NEW · —";
    el.form.reset();
    document.querySelectorAll(".chip[aria-pressed='true']").forEach((c) => c.setAttribute("aria-pressed", "false"));
    state.selectedInterests.clear();
    setDefaultDates();
    document.getElementById("destination").focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function tryResumeSession() {
    if (!state.sessionId) return;
    try {
      const history = await apiFetch(`/trip/session/${state.sessionId}`);
      const messages = history.messages || [];
      if (messages.length === 0) return;

      // First user/assistant pair is the original itinerary request+answer.
      const firstAssistant = messages.find((m) => m.role === "assistant");
      if (firstAssistant) {
        renderTicket({
          destination: state.destination || "Your trip",
          duration_days: 0,
          session_id: state.sessionId,
          tools_used: [],
          itinerary: firstAssistant.content,
        });
        document.getElementById("stub-duration").textContent = "resumed";
        document.getElementById("stub-travelers").textContent = "—";
      }

      // Replay everything after the first pair into the chat log.
      clearLog();
      let seenFirstAssistant = false;
      for (const m of messages) {
        if (!seenFirstAssistant && m.role === "assistant") {
          seenFirstAssistant = true;
          continue;
        }
        if (!seenFirstAssistant) continue; // skip the initial planning prompt (verbose)
        appendMessage(m.role === "user" ? "user" : "agent", m.content);
      }

      el.tower.classList.add("show");
      el.newTripBtn.style.display = "inline-block";
    } catch {
      // Session no longer exists (expired / server restarted) — quietly reset.
      resetSession();
    }
  }

  // ---------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------
  function init() {
    buildInterestChips();
    setDefaultDates();
    startFlipText();
    checkHealth();
    tryResumeSession();

    el.form.addEventListener("submit", handlePlanSubmit);
    el.followupForm.addEventListener("submit", handleFollowupSubmit);
    el.newTripBtn.addEventListener("click", startNewTrip);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
