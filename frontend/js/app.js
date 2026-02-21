// frontend/js/app.js  –  AI Health Partner · Complete Application Logic

const API = "http://localhost:8000/api";
let token       = localStorage.getItem("hp_token");
let currentUser = JSON.parse(localStorage.getItem("hp_user") || "null");
let healthChart = null;
let scoreChart  = null;
let ws          = null;
let malariaMap  = null;

// ═══════════════════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
  if (token && currentUser) showApp();
});

// ═══════════════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════════════
function switchAuthTab(tab) {
  const isLogin = tab === "login";
  document.getElementById("form-login").style.display    = isLogin ? "block" : "none";
  document.getElementById("form-register").style.display = isLogin ? "none"  : "block";
  document.getElementById("tab-login").className    = isLogin ? "btn-primary" : "btn-ghost";
  document.getElementById("tab-register").className = isLogin ? "btn-ghost"   : "btn-primary";
  document.getElementById("tab-login").style.border    = "none";
  document.getElementById("tab-register").style.border = "none";
}

async function doLogin() {
  const btn = document.getElementById("login-btn");
  const email    = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;
  if (!email || !password) return showToast("Please enter your email and password.", "error");

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    const res  = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    saveSession(data);
    showApp();
    showToast("Welcome back! 👋");
  } catch (e) {
    showToast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Sign In";
  }
}

async function doRegister() {
  const btn      = document.getElementById("reg-btn");
  const email    = document.getElementById("reg-email").value.trim();
  const username = document.getElementById("reg-username").value.trim();
  const password = document.getElementById("reg-password").value;

  if (!email || !username || !password)
    return showToast("Email, username and password are required.", "error");

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Creating…';

  try {
    const fd = new FormData();
    fd.append("email",    email);
    fd.append("username", username);
    fd.append("password", password);

    const age    = document.getElementById("reg-age").value;
    const gender = document.getElementById("reg-gender").value;
    const height = document.getElementById("reg-height").value;
    const weight = document.getElementById("reg-weight").value;
    const geno   = document.getElementById("reg-genotype").value;
    const blood  = document.getElementById("reg-blood").value;
    const loc    = document.getElementById("reg-location").value.trim();

    if (age)    fd.append("age",        age);
    if (gender) fd.append("gender",     gender);
    if (height) fd.append("height_cm",  height);
    if (weight) fd.append("weight_kg",  weight);
    if (geno)   fd.append("genotype",   geno);
    if (blood)  fd.append("blood_group", blood);
    if (loc)    fd.append("location",   loc);

    fd.append("family_history", JSON.stringify({
      hypertension: document.getElementById("fh-hyp").checked,
      diabetes:     document.getElementById("fh-diabetes").checked,
    }));

    const reportFile = document.getElementById("reg-medical-report").files?.[0];
    if (reportFile) fd.append("medical_report", reportFile);

    // Do NOT set Content-Type — browser adds correct multipart boundary
    const res  = await fetch(`${API}/auth/register`, { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");
    saveSession(data);
    showApp();
    showToast("Account created! Welcome 🎉");
  } catch (e) {
    showToast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Create Account";
  }
}

function handleReportSelect(input) {
  const label = document.getElementById("report-filename");
  const wrap  = document.getElementById("report-label");
  if (input.files?.[0]) {
    const f = input.files[0];
    label.textContent = `✓ ${f.name} (${(f.size / 1048576).toFixed(1)} MB)`;
    label.style.color = "var(--accent)";
    wrap.style.borderColor = "var(--accent)";
  } else {
    label.textContent = "Click to upload medical report";
    label.style.color = "var(--muted)";
    wrap.style.borderColor = "var(--border)";
  }
}

function saveSession(data) {
  token = data.access_token;
  currentUser = { id: data.user_id, username: data.username, is_premium: data.is_premium };
  localStorage.setItem("hp_token", token);
  localStorage.setItem("hp_user",  JSON.stringify(currentUser));
}

function doLogout() {
  localStorage.removeItem("hp_token");
  localStorage.removeItem("hp_user");
  token = null; currentUser = null;
  if (ws) { try { ws.close(); } catch (_) {} }
  document.getElementById("app").style.display = "none";
  document.getElementById("auth-overlay").style.display = "flex";
}

// ═══════════════════════════════════════════════════════
// APP SHELL
// ═══════════════════════════════════════════════════════
function showApp() {
  document.getElementById("auth-overlay").style.display = "none";
  document.getElementById("app").style.display = "block";
  document.getElementById("sidebar-username").textContent = "@" + currentUser.username;
  document.getElementById("dash-name").textContent        = currentUser.username;
  loadDashboard();
  connectWebSocket();
}

function showPage(name) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  document.getElementById(`page-${name}`).classList.add("active");
  document.getElementById(`nav-${name}`).classList.add("active");

  if (name === "dashboard")   loadDashboard();
  if (name === "prediction")  loadPredictionHistory();
  if (name === "scores")      loadDailyQuestions();
  if (name === "mental")      loadMentalHistory();
  if (name === "leaderboard") loadLeaderboard();
  if (name === "map")         initMap();
  if (name === "premium")     refreshPremiumState();
}

// ═══════════════════════════════════════════════════════
// API HELPER
// ═══════════════════════════════════════════════════════
async function apiFetch(path, opts = {}) {
  const isFormData = opts.body instanceof FormData;
  const headers = { "Authorization": `Bearer ${token}` };
  if (!isFormData) headers["Content-Type"] = "application/json";
  const res = await fetch(`${API}${path}`, { ...opts, headers: { ...headers, ...(opts.headers || {}) } });
  if (res.status === 401) { doLogout(); return null; }
  return res;
}

// ═══════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════
async function loadDashboard() {
  const res = await apiFetch("/users/me");
  if (!res) return;
  const user = await res.json();

  document.getElementById("dash-streak").textContent  = user.streak_days ?? 0;
  document.getElementById("dash-points").textContent  = user.points ?? 0;
  document.getElementById("dash-plan").textContent    = user.is_premium ? "Premium ⭐" : "Free";
  document.getElementById("sidebar-streak").textContent = user.streak_days ?? 0;
  document.getElementById("sidebar-points").textContent = user.points ?? 0;
  currentUser.is_premium = user.is_premium;

  // Weekly trend from daily question history
  const hRes = await apiFetch("/daily-questions/history?limit=14");
  if (hRes && hRes.ok) {
    const raw = await hRes.json();
    const history = Array.isArray(raw) ? raw : [];
    renderHealthChart([...history].reverse());
    if (history.length > 0) {
      const scoreEl = document.getElementById("dash-score");
      if (scoreEl) scoreEl.textContent = history[0].composite_score ?? "—";
    }
  }

  // Latest prediction
  const pRes = await apiFetch("/predictions/?limit=1");
  if (pRes && pRes.ok) {
    const _predRaw = await pRes.json();
    const preds = Array.isArray(_predRaw) ? _predRaw : [];
    if (preds.length > 0) {
      const p = preds[0];
      const lc = { low: "var(--accent)", medium: "var(--warning)", high: "var(--danger)" };
      document.getElementById("dash-latest-pred").innerHTML = `
        <div style="font-weight:700;font-family:'Syne',sans-serif;margin-bottom:12px;">Latest Risk Assessment</div>
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
          <span class="badge badge-${p.risk_level}">${p.risk_level.toUpperCase()}</span>
          <span style="font-weight:600;text-transform:capitalize;">${p.prediction_type}</span>
          <span style="font-size:24px;font-weight:800;color:${lc[p.risk_level]};">${p.risk_percentage}%</span>
        </div>
        <div style="font-size:13px;color:var(--muted);line-height:1.6;">${p.claude_explanation || ""}</div>
      `;
    }
  }

  // Latest mental check-in
  const mRes = await apiFetch("/mental/checkins?limit=1");
  if (mRes && mRes.ok) {
    const _mentRaw = await mRes.json();
    const checkins = Array.isArray(_mentRaw) ? _mentRaw : [];
    if (checkins.length > 0) {
      const c = checkins[0];
      const icons = { positive: "😊", neutral: "😐", negative: "😔" };
      document.getElementById("dash-latest-mental").innerHTML = `
        <div style="font-weight:700;font-family:'Syne',sans-serif;margin-bottom:12px;">Mental Wellness</div>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
          <span style="font-size:28px;">${icons[c.sentiment] || "🧠"}</span>
          <div>
            <div style="font-weight:600;">${c.emotional_state || c.sentiment}</div>
            <div style="font-size:12px;color:var(--muted);">${new Date(c.created_at).toLocaleDateString()}</div>
          </div>
        </div>
        <div style="font-size:13px;color:var(--muted);line-height:1.6;">${c.claude_response || ""}</div>
      `;
    }
  }
}

function renderHealthChart(history) {
  const ctx = document.getElementById("health-chart").getContext("2d");
  if (healthChart) healthChart.destroy();
  if (!history.length) return;

  healthChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: history.map(s => new Date(s.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })),
      datasets: [{
        label: "Health Score",
        data: history.map(s => s.composite_score),
        borderColor: "#00e5a0",
        backgroundColor: "rgba(0,229,160,.08)",
        tension: .4, fill: true,
        pointBackgroundColor: "#00e5a0", pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: "#1a2640" }, ticks: { color: "#64748b" } },
        y: { grid: { color: "#1a2640" }, ticks: { color: "#64748b" }, min: 0, max: 100 },
      },
    },
  });
}

// ═══════════════════════════════════════════════════════
// RISK PREDICTIONS
// ═══════════════════════════════════════════════════════
async function runPrediction(type) {
  const isHyp = type === "hypertension";
  const btnId = isHyp ? "btn-hyp" : "btn-mal";
  const btn   = document.getElementById(btnId);
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Analysing…';

  try {
    const res = await apiFetch("/predictions/", {
      method: "POST",
      body: JSON.stringify({ prediction_type: type }),
    });
    if (!res) return;
    const pred = await res.json();
    if (!res.ok) throw new Error(pred.detail || "Prediction failed");
    displayPrediction(type, pred);
    showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} analysis complete!`);
  } catch (e) {
    showToast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = isHyp ? "Re-Analyse" : "Re-Analyse";
  }
}

function displayPrediction(type, pred) {
  const pfx     = type === "hypertension" ? "hyp" : "mal";
  const resultEl = document.getElementById(`${pfx}-result`);
  resultEl.style.display = "block";

  // Animate ring
  const circ   = 2 * Math.PI * 52;
  const offset = circ - (pred.risk_percentage / 100) * circ;
  document.getElementById(`${pfx}-ring`).style.strokeDashoffset = offset;
  document.getElementById(`${pfx}-pct`).textContent  = pred.risk_percentage + "%";

  const badgeEl = document.getElementById(`${pfx}-badge`);
  badgeEl.textContent = pred.risk_level.charAt(0).toUpperCase() + pred.risk_level.slice(1);
  badgeEl.className   = `badge badge-${pred.risk_level}`;

  document.getElementById(`${pfx}-level`).textContent     = pred.risk_level.toUpperCase() + " RISK";
  document.getElementById(`${pfx}-explanation`).textContent = pred.claude_explanation || "";
  document.getElementById(`${pfx}-advice`).innerHTML = (pred.prevention_advice || "").replace(/\n/g, "<br>");
}

async function loadPredictionHistory() {
  const res = await apiFetch("/predictions/");
  if (!res) return;
  const preds = await res.json();
  const el = document.getElementById("prediction-history");

  if (!preds.length) {
    el.innerHTML = '<div style="color:var(--muted);">No predictions yet. Run an analysis above.</div>';
    return;
  }
  const lc = { low: "var(--accent)", medium: "var(--warning)", high: "var(--danger)" };
  el.innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="color:var(--muted);border-bottom:1px solid var(--border);">
          <th style="text-align:left;padding:8px 0;">Date</th>
          <th style="text-align:left;padding:8px;">Type</th>
          <th style="text-align:left;padding:8px;">Risk %</th>
          <th style="text-align:left;padding:8px;">Level</th>
        </tr>
      </thead>
      <tbody>
        ${preds.map(p => `
          <tr style="border-bottom:1px solid var(--border);">
            <td style="padding:10px 0;color:var(--muted);">${new Date(p.created_at).toLocaleDateString()}</td>
            <td style="padding:10px 8px;text-transform:capitalize;">${p.prediction_type}</td>
            <td style="padding:10px 8px;font-weight:700;color:${lc[p.risk_level]};">${p.risk_percentage}%</td>
            <td style="padding:10px 8px;"><span class="badge badge-${p.risk_level}">${p.risk_level}</span></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

// ═══════════════════════════════════════════════════════
// DAILY GAMIFIED QUESTIONS
// ═══════════════════════════════════════════════════════
let _dailyQuestions = [];
let _userAnswers    = {};

const CAT = {
  diet:     { icon: "🥗", label: "Diet",        color: "#00e5a0" },
  sleep:    { icon: "🌙", label: "Sleep",        color: "#3b82f6" },
  activity: { icon: "🏃", label: "Activity",     color: "#f59e0b" },
  mental:   { icon: "🧠", label: "Mental",       color: "#a855f7" },
  location: { icon: "📍", label: "Environment",  color: "#f43f5e" },
};

async function loadDailyQuestions() {
  _userAnswers = {};
  show("qs-loading"); hide("qs-form"); hide("qs-done");
  loadScoreHistory();

  try {
    const res  = await apiFetch("/daily-questions/today");
    if (!res) return;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Route not found — please restart the backend server (see instructions below)");

    _dailyQuestions = data.questions;

    hide("qs-loading");
    if (data.already_completed) {
      await showCompletedState();
    } else {
      renderQuestions(data.questions);
      document.getElementById("qs-date").textContent =
        new Date().toLocaleDateString("en", { weekday: "long", month: "long", day: "numeric" });
      show("qs-form");
      updateProgress();
    }
  } catch (e) {
    hide("qs-loading");
    showToast("Could not load questions: " + e.message, "error");
  }
}

async function showCompletedState() {
  show("qs-done");
  const res = await apiFetch("/daily-questions/history?limit=1");
  if (!res || !res.ok) return;
  const _h = await res.json();
  const history = Array.isArray(_h) ? _h : [];
  if (!history.length) return;
  populateDoneCard(history[0]);
  showCategoryBreakdown(history[0]);
}

function populateDoneCard(entry) {
  const b = scoreToBadge(entry.composite_score || 0);
  document.getElementById("qs-done-badge-icon").textContent = b.icon;
  document.getElementById("qs-done-badge").textContent      = b.label;
  document.getElementById("qs-done-score").textContent      = entry.composite_score ?? "—";
  document.getElementById("qs-done-msg").textContent        = scoreToMessage(entry.composite_score || 0);

  document.getElementById("qs-done-cats").innerHTML = [
    { key: "sleep_score",    ...CAT.sleep    },
    { key: "diet_score",     ...CAT.diet     },
    { key: "activity_score", ...CAT.activity },
    { key: "mental_score",   ...CAT.mental   },
  ].map(c => `
    <div style="text-align:center;padding:10px;background:var(--surface);border-radius:10px;border:1px solid var(--border);">
      <div style="font-size:20px;">${c.icon}</div>
      <div style="font-size:22px;font-weight:800;color:${c.color};font-family:'Syne',sans-serif;">${entry[c.key] ?? "—"}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:2px;">${c.label}</div>
    </div>
  `).join("");
}

function showCategoryBreakdown(entry) {
  show("qs-category-card");
  document.getElementById("qs-category-bars").innerHTML = [
    { key: "sleep_score",    ...CAT.sleep    },
    { key: "diet_score",     ...CAT.diet     },
    { key: "activity_score", ...CAT.activity },
    { key: "mental_score",   ...CAT.mental   },
  ].map(c => {
    const val = entry[c.key] || 0;
    return `
      <div>
        <div style="display:flex;justify-content:space-between;margin-bottom:5px;font-size:13px;">
          <span>${c.icon} ${c.label}</span>
          <span style="color:${c.color};font-weight:700;">${val}/10</span>
        </div>
        <div class="prog-track">
          <div class="prog-fill" style="background:${c.color};width:${(val / 10) * 100}%;"></div>
        </div>
      </div>`;
  }).join("");
}

function renderQuestions(questions) {
  const container = document.getElementById("qs-questions-list");
  container.innerHTML = "";

  questions.forEach((q, idx) => {
    const meta = CAT[q.category] || { icon: "❓", label: q.category, color: "var(--accent)" };
    const card = document.createElement("div");
    card.className = "card";
    card.id = `q-card-${q.question_id}`;
    card.style.cssText = `padding:20px;border-left:3px solid ${meta.color};`;

    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
        <span style="background:${meta.color}22;color:${meta.color};font-size:11px;font-weight:700;
          padding:3px 10px;border-radius:100px;">${meta.icon} ${meta.label.toUpperCase()}</span>
        <span style="font-size:12px;color:var(--muted);">Q${idx + 1}</span>
      </div>
      <div style="font-weight:600;font-size:15px;margin-bottom:14px;line-height:1.5;">${q.question_text}</div>
      <div style="display:flex;flex-direction:column;gap:8px;" id="opts-${q.question_id}">
        ${q.options.map(opt => `
          <button class="q-option"
            onclick="selectAnswer('${q.question_id}', this)"
            data-qid="${q.question_id}"
            data-label="${opt.label.replace(/"/g, '&quot;')}">
            ${opt.label}
          </button>
        `).join("")}
      </div>
    `;
    container.appendChild(card);
  });
}

function selectAnswer(questionId, btn) {
  document.querySelectorAll(`[data-qid="${questionId}"]`).forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
  _userAnswers[questionId] = btn.dataset.label;
  updateProgress();
}

function updateProgress() {
  const total    = _dailyQuestions.length;
  const answered = Object.keys(_userAnswers).length;
  const pct      = total > 0 ? (answered / total) * 100 : 0;

  document.getElementById("qs-progress-text").textContent = `${answered} / ${total} answered`;
  document.getElementById("qs-progress-bar").style.width  = pct + "%";

  const btn = document.getElementById("qs-submit-btn");
  if (btn) btn.disabled = answered < total;
}

async function submitDailyQuestions() {
  const btn = document.getElementById("qs-submit-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Calculating your score…';

  try {
    const res = await apiFetch("/daily-questions/submit", {
      method: "POST",
      body: JSON.stringify({ answers: _userAnswers }),
    });
    if (!res) return;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Submission failed");

    // Show done card
    hide("qs-form");
    show("qs-done");
    populateDoneCard({
      composite_score: data.composite_score,
      sleep_score:     data.sleep_score,
      diet_score:      data.diet_score,
      activity_score:  data.activity_score,
      mental_score:    data.mental_score,
    });
    showCategoryBreakdown({
      sleep_score:    data.sleep_score,
      diet_score:     data.diet_score,
      activity_score: data.activity_score,
      mental_score:   data.mental_score,
    });

    // ML preview
    document.getElementById("qs-ml-preview").textContent = JSON.stringify({
      date: new Date().toISOString().split("T")[0],
      composite_score: data.composite_score,
      category_scores: {
        sleep:    data.sleep_score,
        diet:     data.diet_score,
        activity: data.activity_score,
        mental:   data.mental_score,
        location: data.location_score,
      },
      note: "ml_features stored server-side for risk model",
    }, null, 2);

    loadScoreHistory();
    showToast(`${data.badge} — Score: ${data.composite_score}/100 🎯`);
  } catch (e) {
    showToast(e.message, "error");
    btn.disabled = false;
    btn.innerHTML = "🎯 Submit & Get Your Score";
  }
}

async function loadScoreHistory() {
  const res = await apiFetch("/daily-questions/history?limit=14");
  if (!res || !res.ok) return;
  const _raw = await res.json();
  const history = Array.isArray(_raw) ? _raw : [];
  const ctx     = document.getElementById("score-chart").getContext("2d");

  if (scoreChart) { scoreChart.destroy(); scoreChart = null; }

  const empty = document.getElementById("score-chart-empty");
  if (!history.length) {
    if (empty) empty.style.display = "block";
    return;
  }
  if (empty) empty.style.display = "none";

  const rev = [...history].reverse();
  scoreChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: rev.map(s => new Date(s.date + "T00:00:00").toLocaleDateString("en", { month: "short", day: "numeric" })),
      datasets: [
        { label: "Sleep",    data: rev.map(s => s.sleep_score),    backgroundColor: "#3b82f688" },
        { label: "Diet",     data: rev.map(s => s.diet_score),     backgroundColor: "#00e5a088" },
        { label: "Activity", data: rev.map(s => s.activity_score), backgroundColor: "#f59e0b88" },
        { label: "Mental",   data: rev.map(s => s.mental_score),   backgroundColor: "#a855f788" },
      ],
    },
    options: {
      responsive: true,
      scales: {
        x: { grid: { color: "#1a2640" }, ticks: { color: "#64748b" } },
        y: { grid: { color: "#1a2640" }, ticks: { color: "#64748b" }, min: 0, max: 10 },
      },
      plugins: { legend: { labels: { color: "#64748b", font: { size: 11 } } } },
    },
  });
}

function scoreToBadge(score) {
  if (score >= 85) return { icon: "🏆", label: "Health Champion"  };
  if (score >= 70) return { icon: "🌟", label: "Wellness Star"    };
  if (score >= 55) return { icon: "💪", label: "Making Progress"  };
  if (score >= 40) return { icon: "🌱", label: "Getting Started"  };
  return               { icon: "❤️", label: "Keep Going"         };
}

function scoreToMessage(score) {
  if (score >= 85) return "Outstanding! You're crushing your health goals today!";
  if (score >= 70) return "Great job! You're building excellent health habits.";
  if (score >= 55) return "Good effort! Small improvements add up over time.";
  if (score >= 40) return "You've made a start — tomorrow is another chance!";
  return "Every day is a new opportunity. You've got this! 💙";
}

// ═══════════════════════════════════════════════════════
// MENTAL CHECK-IN
// ═══════════════════════════════════════════════════════
async function submitMentalCheckin() {
  const input = document.getElementById("mental-input").value.trim();
  if (!input) return showToast("Please describe how you're feeling.", "error");

  const btn = document.getElementById("mental-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Analysing…';

  try {
    const res  = await apiFetch("/mental/checkin", {
      method: "POST",
      body: JSON.stringify({ text_input: input }),
    });
    if (!res) return;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Check-in failed");
    displayMentalResult(data);
    loadMentalHistory();
    showToast("Mental check-in saved 💙");
  } catch (e) {
    showToast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Analyse with AI";
  }
}

function displayMentalResult(data) {
  show("mental-result-card");
  const icons = { positive: "😊", neutral: "😐", negative: "😔" };
  document.getElementById("sentiment-icon").textContent   = icons[data.sentiment] || "🧠";
  document.getElementById("emotional-state").textContent  = data.emotional_state || "";
  document.getElementById("sentiment-label").textContent  =
    data.sentiment ? data.sentiment.charAt(0).toUpperCase() + data.sentiment.slice(1) + " Sentiment" : "";
  document.getElementById("claude-response").textContent  = data.claude_response || "";
  document.getElementById("coping-suggestions").innerHTML = (data.coping_suggestions || "").replace(/\n/g, "<br>");
}

function startVoiceSimulation() {
  const samples = [
    "I've been feeling really stressed lately with work deadlines piling up. I haven't been sleeping well.",
    "Today was actually a good day! I went for a walk and felt more energised than usual.",
    "I feel quite anxious about an upcoming presentation. My heart races whenever I think about it.",
    "Feeling a bit low today. Not sure why. Just unmotivated and tired.",
  ];
  document.getElementById("mental-input").value = samples[Math.floor(Math.random() * samples.length)];
  showToast("🎤 Voice input simulated");
}

async function loadMentalHistory() {
  const res = await apiFetch("/mental/checkins");
  if (!res) return;
  const checkins  = await res.json();
  const container = document.getElementById("mental-history");

  if (!checkins.length) {
    container.innerHTML = '<div style="color:var(--muted);font-size:14px;">No check-ins yet.</div>';
    return;
  }
  const icons = { positive: "😊", neutral: "😐", negative: "😔" };
  container.innerHTML = checkins.map(c => `
    <div style="display:flex;gap:12px;padding:14px 0;border-bottom:1px solid var(--border);">
      <div style="font-size:24px;">${icons[c.sentiment] || "🧠"}</div>
      <div style="flex:1;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <span style="font-weight:600;font-size:14px;">${c.emotional_state || c.sentiment}</span>
          <span style="font-size:12px;color:var(--muted);">${new Date(c.created_at).toLocaleDateString()}</span>
        </div>
        <div style="font-size:13px;color:var(--muted);line-height:1.5;">${(c.text_input || "").substring(0, 120)}…</div>
      </div>
    </div>
  `).join("");
}

// ═══════════════════════════════════════════════════════
// LEADERBOARD
// ═══════════════════════════════════════════════════════
async function loadLeaderboard() {
  const res       = await apiFetch("/gamification/leaderboard");
  if (!res) return;
  const entries   = await res.json();
  const container = document.getElementById("leaderboard-list");

  if (!entries.length) {
    container.innerHTML = '<div style="color:var(--muted);font-size:14px;text-align:center;padding:24px;">No data yet. Complete check-ins to earn points!</div>';
    return;
  }

  const medals = ["🥇", "🥈", "🥉"];
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;margin-bottom:16px;padding-bottom:12px;
      border-bottom:1px solid var(--border);font-size:11px;color:var(--muted);font-weight:700;letter-spacing:.05em;">
      <span>RANK</span><span>USER</span><span>POINTS</span>
    </div>
    ${entries.map(e => `
      <div style="display:flex;align-items:center;padding:12px 8px;border-radius:10px;margin-bottom:4px;
        ${e.username === currentUser?.username ? "background:#00e5a010;border:1px solid #00e5a030;" : ""}">
        <span style="width:36px;font-size:${e.rank <= 3 ? "20px" : "14px"};color:${e.rank > 3 ? "var(--muted)" : ""};font-weight:700;">
          ${e.rank <= 3 ? medals[e.rank - 1] : "#" + e.rank}
        </span>
        <span style="flex:1;font-weight:${e.username === currentUser?.username ? "700" : "400"};
          color:${e.username === currentUser?.username ? "var(--accent)" : "var(--text)"};">
          ${e.username}${e.username === currentUser?.username ? " (you)" : ""}
        </span>
        <span style="font-family:'Syne',sans-serif;font-weight:700;color:var(--accent2);">${(e.points || 0).toLocaleString()}</span>
      </div>
    `).join("")}
  `;
}

// ═══════════════════════════════════════════════════════
// MALARIA MAP
// ═══════════════════════════════════════════════════════
function initMap() {
  if (malariaMap) return;
  malariaMap = L.map("malaria-map", { center: [9.082, 8.6753], zoom: 5 });
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: "© OpenStreetMap contributors © CARTO", maxZoom: 19,
  }).addTo(malariaMap);

  const zones = [
    { lat:  6.5244, lng:  3.3792, level: "high",   name: "Lagos, Nigeria",    detail: "Year-round high transmission. Use nets every night." },
    { lat:  5.5560, lng: -0.1969, level: "high",   name: "Accra, Ghana",      detail: "High risk. Prophylaxis recommended for visitors." },
    { lat:  3.8480, lng: 11.5021, level: "high",   name: "Yaoundé, Cameroon", detail: "Endemic region. Seek treatment within 24h of fever." },
    { lat:  4.3612, lng: 18.5550, level: "high",   name: "Bangui, CAR",       detail: "Very high burden. All prevention measures essential." },
    { lat:  9.0579, lng:  7.4951, level: "medium", name: "Abuja, Nigeria",    detail: "Seasonal risk. Highest Jul–Oct. Use repellents." },
    { lat: 12.0022, lng:  8.5920, level: "medium", name: "Kano, Nigeria",     detail: "Seasonal transmission. Risk peaks in rainy season." },
    { lat:  7.3776, lng:  3.9470, level: "medium", name: "Ibadan, Nigeria",   detail: "Moderate risk. Bed nets recommended." },
    { lat: 14.9213, lng:-23.5087, level: "low",    name: "Praia, Cape Verde", detail: "Low risk. Mainly imported cases." },
    { lat: 31.2001, lng: 29.9187, level: "low",    name: "Alexandria, Egypt", detail: "Very low risk. Mostly P. vivax in Nile delta." },
  ];

  const colors = { high: "#f43f5e", medium: "#f59e0b", low: "#00e5a0" };
  zones.forEach(z => {
    L.circleMarker([z.lat, z.lng], {
      radius: z.level === "high" ? 14 : z.level === "medium" ? 10 : 7,
      fillColor: colors[z.level], color: colors[z.level],
      weight: 2, opacity: .9, fillOpacity: .4,
    }).addTo(malariaMap)
    .bindPopup(`
      <div style="font-family:'DM Sans',sans-serif;min-width:180px;">
        <div style="font-weight:700;margin-bottom:4px;">${z.name}</div>
        <div style="display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700;
          background:${colors[z.level]}22;color:${colors[z.level]};border:1px solid ${colors[z.level]}44;
          margin-bottom:8px;">${z.level.toUpperCase()} RISK</div>
        <div style="font-size:12px;line-height:1.5;color:#666;">${z.detail}</div>
      </div>`);
  });
}

// ═══════════════════════════════════════════════════════
// PREMIUM / PAYMENT
// ═══════════════════════════════════════════════════════
async function initiatePayment() {
  const btn = document.getElementById("pay-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Initiating…';

  try {
    const res  = await apiFetch("/payments/initiate", {
      method: "POST",
      body: JSON.stringify({ amount: 5000 }),
    });
    if (!res) return;
    const data = await res.json();

    if (data.status === "demo") {
      showToast("Demo mode — activating premium…");
      await demoVerifyPayment(data.reference);
    } else {
      window.open(data.authorization_url, "_blank");
      btn.innerHTML = "Verify Payment";
      btn.disabled  = false;
      btn.onclick   = () => promptVerify(data.reference);
    }
  } catch (e) {
    showToast(e.message, "error");
    btn.disabled = false;
    btn.innerHTML = "Upgrade to Premium";
  }
}

async function demoVerifyPayment(reference) {
  const btn = document.getElementById("pay-btn");
  try {
    const res  = await apiFetch("/payments/verify", {
      method: "POST",
      body: JSON.stringify({ reference }),
    });
    if (!res) return;
    const data = await res.json();
    if (data.is_premium) {
      currentUser.is_premium = true;
      localStorage.setItem("hp_user", JSON.stringify(currentUser));
      showToast("🎉 Premium activated! Welcome to the premium plan.");
      refreshPremiumState();
    }
  } catch (e) {
    showToast("Verification failed.", "error");
  } finally {
    btn.disabled  = false;
    btn.innerHTML = "Upgrade to Premium";
  }
}

async function promptVerify(reference) {
  const ref = prompt("Enter your payment reference:", reference);
  if (ref) await demoVerifyPayment(ref);
}

function refreshPremiumState() {
  if (currentUser?.is_premium) {
    show("premium-features");
    const btn    = document.getElementById("pay-btn");
    btn.textContent = "✓ Premium Active";
    btn.disabled    = true;
    document.getElementById("dash-plan").textContent = "Premium ⭐";
  }
}
// ═══════════════════════════════════════════════════════
// WEBSOCKET
// ═══════════════════════════════════════════════════════
function connectWebSocket() {
  if (!token) return;
  try {
    ws = new WebSocket(`ws://localhost:8000/ws/scores?token=${encodeURIComponent(token)}`);
    ws.onopen = () => {
      const el = document.getElementById("ws-indicator");
      if (el) {
        el.innerHTML = `<div style="width:8px;height:8px;border-radius:50%;background:var(--accent);animation:pulse 2s infinite;"></div> Live`;
        el.style.color = "var(--accent)";
      }
      setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send("ping"); }, 30000);
    };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.event === "score_update") {
          showToast(`📊 Score updated: ${msg.data?.composite_score}/100`);
          loadDashboard();
        }
      } catch (_) {}
    };
    ws.onerror = () => {};
  } catch (_) {}
}

// ═══════════════════════════════════════════════════════
// TOAST
// ═══════════════════════════════════════════════════════
let _toastTimer = null;
function showToast(msg, type = "success") {
  const toast  = document.getElementById("toast");
  const colors = { success: "var(--accent)", error: "var(--danger)" };
  toast.style.borderColor = type === "error" ? "var(--danger)" : "var(--border)";
  toast.innerHTML = `<span style="color:${colors[type]};">${type === "error" ? "⚠ " : "✓ "}</span>${msg}`;
  toast.classList.add("show");
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => toast.classList.remove("show"), 3500);
}

// ═══════════════════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════════════════
function show(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "";
}
function hide(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "none";
}