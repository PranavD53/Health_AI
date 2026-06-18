(function () {
  const API_BASE = localStorage.getItem("healthai_api_base") || `${location.origin}`;
  const PAGE = location.pathname.toLowerCase();

  const routes = {
    login: "/frontend/unified_login_flow/code.html",
    dashboard: "/frontend/patient_dashboard/code.html",
    symptoms: "/frontend/ai_symptom_checker/code.html",
    appointments: "/frontend/doctor_search_booking/code.html",
    records: "/frontend/medical_records_rag_chat/code.html",
    profile: "/frontend/patient_registration/code.html",
    doctorDashboard: "/frontend/doctor_dashboard/code.html",
    adminDashboard: "/frontend/admin_dashboard/code.html",
  };

  const demo = {
    patient: { email: "patient@healthai.test", password: "Password123!" },
    doctor: { email: "alice.smith@hospital.com", password: "Password123!" },
    admin: { email: "admin@healthai.test", password: "Password123!" },
  };

  const state = {
    selectedDoctor: null,
    selectedDate: new Date().toISOString().slice(0, 10),
    selectedTime: "10:30",
  };

  function token() {
    return localStorage.getItem("healthai_access_token");
  }

  function role() {
    return localStorage.getItem("healthai_role") || "patient";
  }

  function setSession(data) {
    localStorage.setItem("healthai_access_token", data.access_token);
    localStorage.setItem("healthai_refresh_token", data.refresh_token);
    localStorage.setItem("healthai_role", data.role);
  }

  function logout() {
    if (token()) {
      api("/auth/logout", { method: "POST" }).catch(() => {});
    }
    localStorage.removeItem("healthai_access_token");
    localStorage.removeItem("healthai_refresh_token");
    localStorage.removeItem("healthai_role");
    location.href = routes.login;
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const isFormData = options.body instanceof FormData;

    if (!isFormData && options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (token()) {
      headers.set("Authorization", `Bearer ${token()}`);
    }

    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    let payload = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }

    if (!response.ok) {
      const message = payload && payload.detail ? payload.detail : "Something went wrong. Please try again.";
      if (response.status === 401 && !PAGE.includes("unified_login_flow")) {
        toast("Please log in again.", "error");
        setTimeout(logout, 700);
      }
      throw new Error(Array.isArray(message) ? message.map((item) => item.msg).join(", ") : message);
    }

    return payload;
  }

  function toast(message, type = "success") {
    let host = document.getElementById("healthai-toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "healthai-toast-host";
      host.className = "fixed top-6 right-6 z-[9999] flex flex-col gap-3";
      document.body.appendChild(host);
    }

    const note = document.createElement("div");
    note.className = `max-w-sm rounded-xl border p-4 shadow-2xl bg-white text-sm ${
      type === "error" ? "border-red-200 text-red-800" : "border-teal-200 text-[#00355f]"
    }`;
    note.textContent = message;
    host.appendChild(note);
    setTimeout(() => note.remove(), 4200);
  }

  function textIncludes(element, words) {
    return words.some((word) => (element.textContent || "").trim().toLowerCase().includes(word));
  }

  function wireNavigation() {
    document.querySelectorAll("a, button").forEach((element) => {
      const text = (element.textContent || "").trim().toLowerCase();
      if (!text) return;

      if (text.includes("dashboard") || text === "home" || text.includes("overview")) {
        setClick(element, () => go(role() === "doctor" ? routes.doctorDashboard : role() === "admin" ? routes.adminDashboard : routes.dashboard));
      } else if (text.includes("symptom") || text.includes("start new analysis")) {
        setClick(element, () => go(routes.symptoms));
      } else if (text.includes("appointment") || text.includes("consultation") || text.includes("care finder") || text.includes("find a clinic")) {
        setClick(element, () => go(routes.appointments));
      } else if (text.includes("record") || text.includes("chat")) {
        setClick(element, () => go(text.includes("chat") ? routes.symptoms : routes.records));
      } else if (text.includes("profile") || text.includes("settings")) {
        setClick(element, () => go(routes.profile));
      } else if (text.includes("logout")) {
        setClick(element, logout);
      } else if (text.includes("emergency") || text.includes("sos")) {
        setClick(element, () => toast("Emergency alert noted. Please call 108 or local emergency services now.", "error"));
      } else if (text.includes("help")) {
        setClick(element, () => toast("Help request received. A support workflow can be added here."));
      } else if (text.includes("notification")) {
        setClick(element, () => toast("No new notifications."));
      }
    });
  }

  function setClick(element, handler) {
    element.addEventListener("click", (event) => {
      event.preventDefault();
      handler(event);
    });
  }

  function go(path) {
    location.href = path;
  }

  function requireAuth() {
    if (!PAGE.includes("unified_login_flow") && !token()) {
      location.href = routes.login;
    }
  }

  function wireLogin() {
    if (!PAGE.includes("unified_login_flow")) return;

    Object.entries(demo).forEach(([demoRole, creds]) => {
      const panel = document.getElementById(`panel-${demoRole}`);
      if (!panel) return;

      const inputs = panel.querySelectorAll("input");
      if (inputs[0]) {
        inputs[0].value = creds.email;
        inputs[0].placeholder = creds.email;
        const label = inputs[0].closest(".space-y-xs")?.querySelector("label");
        if (label) label.textContent = "Email Address";
      }
      if (inputs[1]) {
        inputs[1].value = creds.password;
        inputs[1].placeholder = "Password";
      }
    });

    document.querySelectorAll(".tab-content form").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const panel = form.closest(".tab-content");
        const selectedRole = panel?.id?.replace("panel-", "") || "patient";

        if (selectedRole === "admin" && !document.getElementById("admin-otp-stage")?.classList.contains("hidden")) {
          const otp = Array.from(document.querySelectorAll("#admin-otp-stage input")).map((input) => input.value).join("");
          if (otp.length && otp.length < 6) {
            toast("Enter the full 6-digit MFA code.", "error");
            return;
          }
        }

        const inputs = form.querySelectorAll("input");
        const emailInput = Array.from(inputs).find((input) => input.type === "email" || input.value.includes("@")) || inputs[0];
        const passwordInput = Array.from(inputs).find((input) => input.type === "password");
        await login(emailInput?.value || demo[selectedRole].email, passwordInput?.value || demo[selectedRole].password, selectedRole);
      });
    });

    document.querySelectorAll("button").forEach((button) => {
      if (textIncludes(button, ["register account"])) {
        setClick(button, async () => {
          const form = document.querySelector("#panel-patient form");
          const inputs = form.querySelectorAll("input");
          const email = inputs[0]?.value || demo.patient.email;
          const password = inputs[1]?.value || demo.patient.password;
          try {
            await api("/auth/register", {
              method: "POST",
              body: JSON.stringify({ email, password, role: "patient" }),
            });
            toast("Account created. Logging you in...");
            await login(email, password, "patient");
          } catch (error) {
            toast(error.message, "error");
          }
        });
      }
    });
  }

  async function login(email, password, selectedRole) {
    try {
      const data = await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (selectedRole && data.role !== selectedRole) {
        toast(`Logged in as ${data.role}. Redirecting to the matching workspace.`);
      }
      setSession(data);
      go(data.role === "doctor" ? routes.doctorDashboard : data.role === "admin" ? routes.adminDashboard : routes.dashboard);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function loadDashboard() {
    if (!PAGE.includes("patient_dashboard")) return;
    try {
      const [dashboard, profile] = await Promise.all([
        api("/dashboard"),
        api("/profile").catch(() => null),
      ]);

      const heading = document.querySelector("main h1");
      if (heading && profile?.name) heading.textContent = `Welcome back, ${profile.name.split(" ")[0]}`;

      const subtitle = document.querySelector("main h1 + p");
      if (subtitle) {
        subtitle.textContent = `${dashboard.upcoming_appointments.length} upcoming appointment(s), ${dashboard.recent_symptom_logs.length} recent symptom check(s), and ${dashboard.medical_records.length} record(s).`;
      }

      const appointmentBox = Array.from(document.querySelectorAll("h2")).find((h) => h.textContent.includes("Upcoming Appointments"))?.closest(".md\\:col-span-8");
      if (appointmentBox) {
        appointmentBox.querySelector(".space-y-md").innerHTML = dashboard.upcoming_appointments.length
          ? dashboard.upcoming_appointments.map(renderAppointment).join("")
          : emptyState("No upcoming appointments yet.", "Book New Consultation");
      }

      const insightTitle = document.querySelector(".bg-primary h2");
      const insightBody = document.querySelector(".bg-primary p.font-body-md");
      if (insightTitle) insightTitle.textContent = "Daily health tip";
      if (insightBody) insightBody.textContent = dashboard.health_tip;

      const symptomCard = Array.from(document.querySelectorAll("h2")).find((h) => h.textContent.includes("Symptom History"))?.closest(".md\\:col-span-5");
      if (symptomCard) {
        const latest = dashboard.recent_symptom_logs[0];
        const badge = symptomCard.querySelector(".rounded-full");
        if (badge) badge.textContent = latest ? latest.risk_category : "Clear";
        const title = symptomCard.querySelector(".p-lg p.font-bold");
        const body = symptomCard.querySelector(".p-lg p.text-label-md");
        if (title) title.textContent = latest ? `Analysis: ${latest.symptoms}` : "No symptom checks yet";
        if (body) body.textContent = latest ? `${latest.severity} severity for ${latest.duration}.` : "Start a new analysis when you need guidance.";
      }

      // Populate metrics
      if (dashboard.metrics) {
        const hrLabel = Array.from(document.querySelectorAll("p")).find(el => el.textContent.trim() === "Heart Rate");
        if (hrLabel && hrLabel.nextElementSibling) {
          hrLabel.nextElementSibling.innerHTML = `${dashboard.metrics.heart_rate.replace(" bpm", "")} <span class="text-label-md font-normal text-on-surface-variant">bpm</span>`;
        }

        const sleepLabel = Array.from(document.querySelectorAll("p")).find(el => el.textContent.trim() === "Sleep Quality");
        if (sleepLabel && sleepLabel.nextElementSibling) {
          const parts = dashboard.metrics.sleep.split(" ");
          const val = parts[0] || "7h 45m";
          const typ = parts.slice(1).join(" ") || "Deep";
          sleepLabel.nextElementSibling.innerHTML = `${val} <span class="text-label-md font-normal text-on-surface-variant">${typ}</span>`;
        }

        const stepsLabel = Array.from(document.querySelectorAll("p")).find(el => el.textContent.trim() === "Daily Steps");
        if (stepsLabel && stepsLabel.nextElementSibling) {
          const parts = dashboard.metrics.steps.split(" ");
          const val = parts[0] || "8,432";
          stepsLabel.nextElementSibling.innerHTML = `${val} <span class="text-label-md font-normal text-on-surface-variant">steps</span>`;
        }
      }

      // Populate timeline logs
      if (dashboard.activity_logs) {
        const timelineHeader = Array.from(document.querySelectorAll("h2")).find(h => h.textContent.includes("Activity Log"));
        if (timelineHeader) {
          const timelineContainer = timelineHeader.nextElementSibling;
          if (timelineContainer) {
            timelineContainer.innerHTML = dashboard.activity_logs.map(log => {
              let icon = "info";
              let colorClass = "bg-primary-fixed text-on-primary-fixed";
              if (log.action.includes("Symptom") || log.action.includes("SYMPTOM") || log.action.includes("CHECK")) {
                icon = "medical_information";
                colorClass = "bg-secondary-fixed text-on-secondary-fixed";
              } else if (log.action.includes("Appointment") || log.action.includes("APPOINTMENT") || log.action.includes("BOOK")) {
                icon = "calendar_today";
                colorClass = "bg-surface-container-highest text-on-surface-variant";
              } else if (log.action.includes("Record") || log.action.includes("RECORD") || log.action.includes("Upload")) {
                icon = "description";
                colorClass = "bg-primary-fixed text-on-primary-fixed";
              } else if (log.action.includes("Profile") || log.action.includes("PROFILE")) {
                icon = "person";
                colorClass = "bg-surface-container-highest text-on-surface-variant";
              }
              const dateObj = new Date(log.timestamp);
              const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
              const dateStr = dateObj.toLocaleDateString([], { month: 'short', day: 'numeric' });
              return `
                <div class="relative pl-10">
                  <div class="absolute left-0 top-1 w-6 h-6 rounded-full ${colorClass} flex items-center justify-center ring-4 ring-surface-container-lowest">
                    <span class="material-symbols-outlined text-[14px]">${icon}</span>
                  </div>
                  <p class="text-label-md font-bold text-on-surface">${log.action}</p>
                  <p class="text-label-sm text-on-surface-variant">${log.details || ""}</p>
                  <p class="text-[10px] text-outline">${dateStr}, ${timeStr}</p>
                </div>
              `;
            }).join("");
          }
        }
      }
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function renderAppointment(item) {
    return `
      <div class="flex items-center gap-lg p-md rounded-2xl bg-surface-container-low border border-outline-variant/40 hover:border-secondary transition-colors">
        <div class="w-16 h-16 rounded-xl bg-primary-fixed flex items-center justify-center text-primary flex-shrink-0">
          <span class="material-symbols-outlined">medical_services</span>
        </div>
        <div class="flex-1">
          <p class="text-body-md font-bold text-on-surface">${item.doctor?.name || "Doctor"}</p>
          <p class="text-label-md text-on-surface-variant">${item.doctor?.specialization || "Consultation"} - ${item.status}</p>
        </div>
        <div class="text-right">
          <p class="text-body-md font-bold text-primary">${item.date}</p>
          <p class="text-label-md text-on-surface-variant">${item.time}</p>
        </div>
        <button class="material-symbols-outlined text-outline hover:text-error" data-cancel-appointment="${item.id}">close</button>
      </div>
    `;
  }

  function emptyState(message, action) {
    return `<div class="p-lg rounded-2xl bg-surface-container-low border border-outline-variant/40 text-on-surface-variant">${message}${action ? ` <button class="text-secondary font-bold">${action}</button>` : ""}</div>`;
  }

  async function loadDoctors() {
    if (!PAGE.includes("doctor_search_booking")) return;
    const grid = document.querySelector("section.grid.grid-cols-1.md\\:grid-cols-2");
    const searchInput = document.querySelector('input[placeholder*="Cardiologist"], input[placeholder*="Smith"]');
    const searchButton = Array.from(document.querySelectorAll("button")).find((button) => button.textContent.trim().toLowerCase().includes("search"));

    async function refresh() {
      try {
        const query = searchInput?.value?.trim() || "";
        const doctors = await api(`/doctors${query ? `?specialization=${encodeURIComponent(query)}` : ""}`);
        if (grid) grid.innerHTML = doctors.map(renderDoctor).join("");
      } catch (error) {
        toast(error.message, "error");
      }
    }

    searchButton?.addEventListener("click", (event) => {
      event.preventDefault();
      refresh();
    });
    searchInput?.addEventListener("input", () => refresh());
    document.querySelectorAll(".flex-none").forEach((card) => {
      card.addEventListener("click", () => {
        if (searchInput) searchInput.value = card.textContent.trim();
        refresh();
      });
    });
    await refresh();
  }

  function renderDoctor(doctor) {
    const disabled = !doctor.available;
    return `
      <div class="doctor-card bg-surface-container-lowest rounded-3xl overflow-hidden shadow-[0px_2px_10px_rgba(15,76,129,0.05)] border border-outline-variant/30 flex flex-col h-full group">
        <div class="relative h-48 overflow-hidden bg-primary-fixed flex items-center justify-center">
          <span class="material-symbols-outlined text-primary text-7xl">medical_services</span>
          <div class="absolute top-md right-md bg-white/90 backdrop-blur-md px-sm py-1 rounded-lg flex items-center gap-xs font-bold text-primary">
            <span class="material-symbols-outlined text-yellow-500 text-[18px]" style="font-variation-settings: 'FILL' 1;">star</span>4.${doctor.id + 4} (${doctor.experience_years} yrs)
          </div>
        </div>
        <div class="p-lg flex flex-col flex-1">
          <div class="mb-md">
            <h3 class="text-title-md font-title-md text-on-surface">${doctor.name}</h3>
            <p class="text-secondary font-bold text-label-md">${doctor.specialization}</p>
          </div>
          <div class="space-y-sm text-body-md text-on-surface-variant flex-1">
            <div class="flex items-center gap-sm"><span class="material-symbols-outlined text-outline text-[20px]">apartment</span><span>${doctor.location}</span></div>
            <div class="flex items-center gap-sm"><span class="material-symbols-outlined text-outline text-[20px]">schedule</span><span>${doctor.experience_years} Years Experience</span></div>
            <div class="flex items-center gap-sm"><span class="material-symbols-outlined text-outline text-[20px]">mail</span><span>${doctor.contact}</span></div>
          </div>
          <div class="mt-lg pt-lg border-t border-outline-variant flex gap-md">
            <button class="book-btn flex-1 ${disabled ? "bg-outline-variant text-on-surface-variant" : "bg-secondary text-on-secondary"} py-md rounded-xl font-bold transition-all" ${disabled ? "disabled" : ""} data-book-doctor="${doctor.id}">${disabled ? "Unavailable" : "Book Appointment"}</button>
            <button class="w-12 h-12 flex items-center justify-center border border-outline-variant rounded-xl text-primary hover:bg-surface-container transition-colors" data-doctor-info="${doctor.id}">
              <span class="material-symbols-outlined">info</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }

  async function bookAppointment() {
    if (!state.selectedDoctor) return;
    try {
      await api("/appointment/book", {
        method: "POST",
        body: JSON.stringify({
          doctor_id: state.selectedDoctor.id,
          date: state.selectedDate,
          time: state.selectedTime,
        }),
      });
      closeNativeBookingModal();
      toast("Booking confirmed. It now appears on your dashboard.");
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function wireAppointmentDelegates() {
    if (!PAGE.includes("doctor_search_booking") && !PAGE.includes("patient_dashboard")) return;
    document.addEventListener("click", async (event) => {
      const bookButton = event.target.closest("[data-book-doctor]");
      if (bookButton) {
        const doctorId = Number(bookButton.dataset.bookDoctor);
        const doctors = await api("/doctors");
        state.selectedDoctor = doctors.find((doctor) => doctor.id === doctorId);
        const modalName = document.getElementById("modalDoctorName");
        if (modalName) modalName.textContent = state.selectedDoctor.name;
        document.getElementById("bookingModal")?.classList.remove("hidden");
        document.body.classList.add("overflow-hidden");
      }

      const cancelButton = event.target.closest("[data-cancel-appointment]");
      if (cancelButton) {
        await api(`/appointment/cancel/${cancelButton.dataset.cancelAppointment}`, { method: "DELETE" });
        toast("Appointment cancelled.");
        loadDashboard();
      }
    });

    document.querySelectorAll("#bookingModal .grid.grid-cols-7 div").forEach((day) => {
      if (/^\d+$/.test(day.textContent.trim())) {
        day.addEventListener("click", () => {
          const selected = String(day.textContent.trim()).padStart(2, "0");
          const now = new Date();
          state.selectedDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${selected}`;
          document.querySelectorAll("#bookingModal .grid.grid-cols-7 div").forEach((el) => el.classList.remove("bg-secondary", "text-on-secondary"));
          day.classList.add("bg-secondary", "text-on-secondary");
        });
      }
    });

    document.querySelectorAll("#bookingModal .grid.grid-cols-2 button").forEach((slot) => {
      slot.addEventListener("click", () => {
        const value = slot.textContent.trim();
        if (slot.disabled || value.includes("04:00")) return;
        state.selectedTime = to24Hour(value);
        document.querySelectorAll("#bookingModal .grid.grid-cols-2 button").forEach((el) => el.classList.remove("border-secondary", "bg-secondary-container", "ring-2"));
        slot.classList.add("border-secondary", "bg-secondary-container", "ring-2");
      });
    });

    window.confirmBooking = bookAppointment;
  }

  function closeNativeBookingModal() {
    document.getElementById("bookingModal")?.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  function to24Hour(value) {
    const [time, meridiem] = value.split(" ");
    let [hours, minutes] = time.split(":").map(Number);
    if (meridiem === "PM" && hours < 12) hours += 12;
    if (meridiem === "AM" && hours === 12) hours = 0;
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
  }

  function wireSymptomChecker() {
    if (!PAGE.includes("ai_symptom_checker")) return;
    const chatInput = document.querySelector('input[placeholder*="Type a symptom"]');
    const sendButton = chatInput?.nextElementSibling;

    async function runQuickCheck() {
      const symptoms = chatInput.value.trim();
      if (!symptoms) return;
      chatInput.value = "";
      appendChat(symptoms, "user");
      const result = await api("/symptom/analyze", {
        method: "POST",
        body: JSON.stringify({ symptoms, duration: "unspecified", severity: "moderate" }),
      });
      showSymptomResult(result);
    }

    sendButton?.addEventListener("click", (event) => {
      event.preventDefault();
      runQuickCheck().catch((error) => toast(error.message, "error"));
    });
    chatInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runQuickCheck().catch((error) => toast(error.message, "error"));
      }
    });

    window.nextStep = async function (step) {
      if (step !== "complete") {
        return window.__originalNextStep ? window.__originalNextStep(step) : null;
      }
      const inputs = Array.from(document.querySelectorAll("#chat-container input, #chat-container select"));
      const symptom = inputs.find((input) => input.placeholder?.includes("Headache"))?.value || chatInput?.value || "general discomfort";
      const duration = inputs.find((input) => input.tagName === "SELECT" && !input.closest("#step-1"))?.value || "1-3 days";
      const severityValue = document.querySelector('input[type="range"]')?.value || "5";
      const severity = Number(severityValue) >= 8 ? "severe" : Number(severityValue) >= 4 ? "moderate" : "mild";
      const result = await api("/symptom/analyze", {
        method: "POST",
        body: JSON.stringify({ symptoms: symptom, duration, severity }),
      });
      showSymptomResult(result);
    };
  }

  function appendChat(message, side) {
    const container = document.getElementById("chat-container");
    if (!container) return;
    const wrapper = document.createElement("div");
    wrapper.className = side === "user" ? "flex flex-col items-end gap-sm" : "flex gap-sm max-w-[85%]";
    wrapper.innerHTML = `<div class="${side === "user" ? "chat-bubble-user border border-outline-variant" : "chat-bubble-ai"} p-md text-on-surface text-body-md">${message}</div>`;
    container.appendChild(wrapper);
    container.scrollTop = container.scrollHeight;
  }

  function showSymptomResult(result) {
    appendChat(result.ai_recommendation || result.alert_message || "Assessment complete.", "ai");
    const section = document.getElementById("results-section");
    if (section) {
      section.classList.remove("hidden");
      const badge = section.querySelector(".rounded-full.font-bold");
      const title = section.querySelector("h4");
      const body = section.querySelector("h4 + p");
      if (badge) badge.textContent = result.symptom_log.risk_category;
      if (title) title.innerHTML = `<span class="material-symbols-outlined text-secondary">info</span> ${result.emergency_alert ? "Emergency symptoms detected" : "Assessment saved"}`;
      if (body) body.textContent = result.ai_recommendation || result.alert_message || result.disclaimer;
      section.scrollIntoView({ behavior: "smooth" });
    }
    const recommendations = document.getElementById("recommendation-list");
    if (recommendations) {
      recommendations.innerHTML = `
        <div class="p-sm bg-surface rounded-lg flex items-center gap-md">
          <span class="material-symbols-outlined text-secondary">event</span>
          <div><p class="text-label-md font-bold">${result.emergency_alert ? "Seek urgent help" : "Book care if needed"}</p><p class="text-[10px] text-outline">${result.symptom_log.risk_category}</p></div>
        </div>
        <div class="p-sm bg-surface rounded-lg flex items-center gap-md">
          <span class="material-symbols-outlined text-secondary">history</span>
          <div><p class="text-label-md font-bold">Saved to history</p><p class="text-[10px] text-outline">${result.symptom_log.created_at}</p></div>
        </div>
      `;
    }
    toast("Symptom analysis saved.");
  }

  function wireRecordsAndChat() {
    if (!PAGE.includes("medical_records_rag_chat")) return;
    const fileInput = document.querySelector('input[type="file"]');
    const uploadButton = Array.from(document.querySelectorAll("button")).find((button) => textIncludes(button, ["upload"]));
    const chatInput = document.querySelector('input[placeholder*="Ask"], textarea[placeholder*="Ask"]');
    const sendButton = chatInput?.nextElementSibling || Array.from(document.querySelectorAll("button")).find((button) => textIncludes(button, ["send"]));

    async function refreshRecords() {
      const records = await api("/records/my-records");
      const target = Array.from(document.querySelectorAll("section, div")).find((el) => textIncludes(el, ["recent documents", "medical records"])) || document.querySelector("main");
      if (!target) return;
      let list = document.getElementById("records-list");
      if (!list) {
        list = document.createElement("div");
        list.id = "records-list";
        list.className = "mt-md space-y-sm";
        target.appendChild(list);
      }
      list.innerHTML = records.length
        ? records.map((record) => `<div class="p-md rounded-xl bg-surface-container-low border border-outline-variant">${record.file_name}<div class="text-xs text-outline">${new Date(record.uploaded_at).toLocaleString()}</div></div>`).join("")
        : `<div class="p-md rounded-xl bg-surface-container-low border border-outline-variant text-on-surface-variant">No records uploaded yet.</div>`;
    }

    uploadButton?.addEventListener("click", async (event) => {
      event.preventDefault();
      if (!fileInput?.files?.[0]) {
        toast("Choose a medical record file first.", "error");
        return;
      }
      const form = new FormData();
      form.append("file", fileInput.files[0]);
      await api("/records/upload", { method: "POST", body: form });
      toast("Record uploaded.");
      refreshRecords();
    });

    sendButton?.addEventListener("click", async (event) => {
      event.preventDefault();
      const message = chatInput?.value?.trim();
      if (!message) return;
      const data = await api("/ai/chat", { method: "POST", body: JSON.stringify({ message }) });
      toast(data.reply);
      chatInput.value = "";
    });

    refreshRecords().catch(() => {});
  }

  async function wireProfile() {
    if (!PAGE.includes("patient_registration")) return;
    const form = document.querySelector("form") || document.querySelector("main");
    if (!form) return;

    if (document.getElementById("email") && document.getElementById("password")) {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const name = document.getElementById("fullName")?.value?.trim();
        const email = document.getElementById("email")?.value?.trim();
        const password = document.getElementById("password")?.value;
        const confirmPassword = document.getElementById("confirmPassword")?.value;
        const terms = document.getElementById("terms");

        if (!name || !email || !password) {
          toast("Please complete the required registration fields.", "error");
          return;
        }
        if (password !== confirmPassword) {
          toast("Passwords do not match.", "error");
          return;
        }
        if (terms && !terms.checked) {
          toast("Please accept the terms to continue.", "error");
          return;
        }

        try {
          try {
            await api("/auth/register", {
              method: "POST",
              body: JSON.stringify({ email, password, role: "patient" }),
            });
          } catch (error) {
            if (!error.message.toLowerCase().includes("already registered")) throw error;
          }

          const session = await api("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
          });
          setSession(session);

          try {
            await api("/profile", {
              method: "POST",
              body: JSON.stringify({ name }),
            });
          } catch (error) {
            if (error.message.toLowerCase().includes("already exists")) {
              await api("/profile", {
                method: "PUT",
                body: JSON.stringify({ name }),
              });
            } else {
              throw error;
            }
          }

          toast("Account ready. Welcome to HealthAI.");
          go(routes.dashboard);
        } catch (error) {
          toast(error.message, "error");
        }
      });
      return;
    }

    try {
      const profile = await api("/profile");
      fillProfile(profile);
    } catch {
      // A missing profile is expected for newly registered users.
    }

    const submitButton = Array.from(document.querySelectorAll("button")).find((button) => textIncludes(button, ["submit", "save", "register", "continue"]));
    submitButton?.addEventListener("click", async (event) => {
      event.preventDefault();
      const profile = collectProfile();
      if (!profile.name) {
        toast("Please enter your name.", "error");
        return;
      }
      try {
        await api("/profile", { method: "PUT", body: JSON.stringify(profile) });
      } catch (error) {
        if (error.message.toLowerCase().includes("not found")) {
          await api("/profile", { method: "POST", body: JSON.stringify(profile) });
        } else {
          throw error;
        }
      }
      toast("Profile saved.");
      go(routes.dashboard);
    });
  }

  function fillProfile(profile) {
    const inputs = Array.from(document.querySelectorAll("input, textarea, select"));
    const values = [profile.name, profile.date_of_birth, profile.gender, profile.height, profile.weight, profile.allergies, profile.existing_conditions];
    inputs.forEach((input, index) => {
      if (values[index] !== null && values[index] !== undefined) input.value = values[index];
    });
  }

  function collectProfile() {
    const inputs = Array.from(document.querySelectorAll("input, textarea, select"));
    return {
      name: inputs[0]?.value || "Patient",
      date_of_birth: inputs[1]?.value || null,
      gender: inputs[2]?.value || null,
      height: inputs[3]?.value ? Number(inputs[3].value) : null,
      weight: inputs[4]?.value ? Number(inputs[4].value) : null,
      allergies: inputs[5]?.value || null,
      existing_conditions: inputs[6]?.value || null,
    };
  }

  // --- Doctor Dashboard Renderers & Loader ---
  function renderDoctorAppointmentRow(appt) {
    const initials = appt.patient_name.split(" ").map(w => w[0]).join("").toUpperCase();
    const priorityColor = appt.priority === "High" ? "text-error" : appt.priority === "Low" ? "text-outline" : "text-secondary";
    const priorityBadge = appt.priority === "High" ? "bg-error" : appt.priority === "Low" ? "bg-outline" : "bg-secondary";
    return `
      <tr class="hover:bg-surface-container-low transition-colors">
        <td class="px-lg py-4">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center text-primary text-[12px] font-bold">${initials}</div>
            <div>
              <p class="text-label-md font-bold">${appt.patient_name}</p>
              <p class="text-label-sm text-outline">${appt.patient_gender} | DOB: ${appt.patient_dob}</p>
            </div>
          </div>
        </td>
        <td class="px-lg py-4">
          <p class="text-label-md">${appt.time}</p>
          <p class="text-label-sm text-outline">${appt.date}</p>
        </td>
        <td class="px-lg py-4">
          <span class="px-3 py-1 bg-surface-container-high rounded-full text-label-sm text-on-surface-variant border border-outline-variant">${appt.type}</span>
        </td>
        <td class="px-lg py-4">
          <div class="flex items-center gap-1.5 ${priorityColor}">
            <span class="w-2 h-2 rounded-full ${priorityBadge}"></span>
            <span class="text-label-sm font-bold">${appt.priority}</span>
          </div>
        </td>
        <td class="px-lg py-4 text-right">
          <button class="text-primary hover:underline text-label-md font-bold" onclick="toast('Starting session...')">Start Session</button>
        </td>
      </tr>
    `;
  }

  function renderPatientSummaryCard(patient) {
    const initials = patient.name.split(" ").map(w => w[0]).join("").toUpperCase();
    return `
      <div class="glass-panel rounded-xl p-lg flex flex-col gap-md hover:shadow-lg transition-all border-l-4 border-primary">
        <div class="flex justify-between items-start">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-full bg-primary-container text-white flex items-center justify-center font-bold">${initials}</div>
            <div>
              <p class="text-title-md font-bold">${patient.name}</p>
              <p class="text-label-sm text-outline">ID: #PX-${patient.user_id}</p>
            </div>
          </div>
          <span class="bg-primary/10 text-primary text-[10px] px-2 py-1 rounded font-bold uppercase">Stable</span>
        </div>
        <div class="grid grid-cols-2 gap-sm text-label-sm">
          <div class="p-2 bg-surface-container rounded-lg">
            <p class="text-outline">Last Visit</p>
            <p class="font-bold">${patient.last_visit}</p>
          </div>
          <div class="p-2 bg-surface-container rounded-lg">
            <p class="text-outline">Primary Concern</p>
            <p class="font-bold truncate" title="${patient.existing_conditions}">${patient.existing_conditions}</p>
          </div>
        </div>
        <button class="w-full flex items-center justify-center gap-2 py-2 bg-surface text-primary border border-primary rounded-lg font-bold hover:bg-primary/5 transition-colors" onclick="toast('Loading clinical records...')">
          <span class="material-symbols-outlined text-[18px]">folder_open</span>
          Full Medical History
        </button>
      </div>
    `;
  }

  async function loadDoctorDashboard() {
    if (!PAGE.includes("doctor_dashboard")) return;
    try {
      const data = await api("/doctor/dashboard");
      
      const docNameEl = Array.from(document.querySelectorAll("h3")).find(h => h.textContent.trim().startsWith("Dr. Sarah") || h.textContent.includes("Jenkins") || h.textContent.includes("Dr."));
      if (docNameEl) docNameEl.textContent = data.name;
      
      const docSpecEl = document.querySelector(".text-secondary.font-label-md");
      if (docSpecEl) docSpecEl.textContent = data.specialization;
      
      const docLicEl = document.querySelector(".text-outline.text-label-sm");
      if (docLicEl) docLicEl.textContent = `License: ${data.license_number}`;

      const consultBox = Array.from(document.querySelectorAll("p")).find(p => p.textContent.includes("Consultations"))?.previousElementSibling;
      if (consultBox) consultBox.textContent = data.consultations_count;

      const tableBody = document.querySelector("table tbody");
      if (tableBody) {
        tableBody.innerHTML = data.upcoming_appointments.length
          ? data.upcoming_appointments.map(renderDoctorAppointmentRow).join("")
          : `<tr><td colspan="5" class="p-lg text-center text-on-surface-variant">No assigned appointments today.</td></tr>`;
      }

      const summariesGrid = Array.from(document.querySelectorAll("h3")).find(h => h.textContent.includes("Patient Medical Summary"))?.closest("div").nextElementSibling;
      if (summariesGrid) {
        summariesGrid.innerHTML = data.patient_summaries.length
          ? data.patient_summaries.map(renderPatientSummaryCard).join("")
          : `<div class="col-span-3 p-lg text-center text-on-surface-variant bg-surface-container rounded-xl">No patients in registry.</div>`;
      }
    } catch (error) {
      toast(error.message, "error");
    }
  }

  // --- Admin Dashboard Renderers & Loader ---
  function renderAdminQueueCard(item) {
    const timeAgo = new Date(item.submitted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `
      <div class="flex flex-col md:flex-row items-center gap-6 p-8 border-b border-outline-variant/10 hover:bg-surface-container-low/30 transition-colors">
        <div class="w-24 h-24 rounded-lg bg-surface-container flex items-center justify-center shrink-0 border border-outline-variant">
          <span class="material-symbols-outlined text-primary text-5xl">medical_services</span>
        </div>
        <div class="flex-grow">
          <div class="flex justify-between items-start mb-2">
            <div>
              <h4 class="text-body-lg font-bold text-on-surface">${item.doctor_name}</h4>
              <p class="text-label-md font-label-md text-secondary">${item.specialization} • ${item.experience_years} yrs exp</p>
            </div>
            <span class="px-3 py-1 bg-surface-container-high text-on-surface-variant text-label-sm rounded-full">Submitted ${timeAgo}</span>
          </div>
          <div class="flex gap-4 mt-4">
            <button class="flex items-center gap-2 text-label-md font-label-md text-primary bg-primary/5 px-4 py-2 rounded-lg hover:bg-primary/10 transition-colors">
              <span class="material-symbols-outlined text-[18px]">description</span> Medical_License.pdf
            </button>
          </div>
        </div>
        <div class="flex flex-row md:flex-col gap-2 shrink-0">
          <button class="px-6 py-2 bg-secondary text-on-secondary rounded-lg font-bold hover:bg-secondary/90 transition-all active:scale-95" data-verify-doc="${item.id}" data-verify-status="verified">Approve</button>
          <button class="px-6 py-2 border border-error text-error rounded-lg font-bold hover:bg-error/5 transition-all" data-verify-doc="${item.id}" data-verify-status="rejected">Decline</button>
        </div>
      </div>
    `;
  }

  function renderAdminUserRow(user) {
    const initials = (user.email || "US").slice(0, 2).toUpperCase();
    const badgeClass = user.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800";
    const statusText = user.is_active ? "Active" : "Inactive";
    return `
      <tr class="hover:bg-surface-container-lowest transition-colors">
        <td class="px-8 py-5">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-[10px]">${initials}</div>
            <div>
              <p class="text-label-md font-bold text-on-surface">${user.email.split("@")[0]}</p>
              <p class="text-label-sm font-label-sm text-outline">${user.email}</p>
            </div>
          </div>
        </td>
        <td class="px-8 py-5 text-label-md text-on-surface-variant capitalize">${user.role}</td>
        <td class="px-8 py-5">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${badgeClass}">${statusText}</span>
        </td>
        <td class="px-8 py-5 text-label-md text-on-surface-variant">Registered</td>
        <td class="px-8 py-5 text-right">
          <div class="flex justify-end gap-3">
            <button class="material-symbols-outlined text-outline hover:text-primary transition-colors" onclick="toast('Editing disabled for security.')">edit</button>
            <button class="material-symbols-outlined text-outline hover:text-error transition-colors" onclick="toast('Blocking user ${user.email}...')">block</button>
          </div>
        </td>
      </tr>
    `;
  }

  function renderAdminAuditLogItem(log, index, total) {
    let color = "bg-primary";
    if (log.action.includes("ERROR") || log.action.includes("FAIL")) {
      color = "bg-error";
    } else if (log.action.includes("LOGIN") || log.action.includes("VERIFY")) {
      color = "bg-secondary";
    } else if (log.action.includes("REGISTER") || log.action.includes("CREATE")) {
      color = "bg-green-500";
    }
    const timeStr = new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isLast = index === total - 1;
    const lineClass = isLast ? "" : "before:content-[''] before:absolute before:left-0 before:top-2 before:bottom-0 before:w-[1px] before:bg-outline-variant/30";
    return `
      <div class="relative pl-6 ${lineClass}">
        <div class="absolute left-[-4px] top-1 w-2 h-2 rounded-full ${color}"></div>
        <p class="text-label-sm font-label-sm text-outline mb-1">${timeStr} - ${log.action}</p>
        <p class="text-label-md font-bold text-on-surface">${log.action.replace(/_/g, " ")}</p>
        <p class="text-label-sm font-label-sm text-on-surface-variant mt-1">${log.details || ""}</p>
      </div>
    `;
  }

  async function loadAdminDashboard() {
    if (!PAGE.includes("admin_dashboard")) return;
    try {
      const data = await api("/admin/dashboard");
      
      const statsBoxes = document.querySelectorAll(".text-headline-lg");
      if (statsBoxes[0]) statsBoxes[0].textContent = data.total_patients;
      if (statsBoxes[1]) statsBoxes[1].textContent = data.total_doctors;
      if (statsBoxes[2]) statsBoxes[2].textContent = data.pending_verifications;
      if (statsBoxes[3]) statsBoxes[3].textContent = data.active_sessions;

      const queueContainer = document.querySelector("section.bg-surface div.p-0");
      if (queueContainer) {
        queueContainer.innerHTML = data.verification_queue.length
          ? data.verification_queue.map(renderAdminQueueCard).join("")
          : `<div class="p-8 text-center text-on-surface-variant font-bold">Verification queue is empty!</div>`;
      }

      const userTableBody = document.querySelector("table tbody");
      if (userTableBody) {
        userTableBody.innerHTML = data.users.length
          ? data.users.map(renderAdminUserRow).join("")
          : `<tr><td colspan="5" class="p-lg text-center text-on-surface-variant">No users registered yet.</td></tr>`;
      }

      const auditContainer = document.querySelector(".flex-grow.overflow-y-auto.max-h-\\[800px\\]");
      if (auditContainer) {
        auditContainer.innerHTML = data.audit_logs.length
          ? data.audit_logs.map((log, idx, arr) => renderAdminAuditLogItem(log, idx, arr.length)).join("")
          : `<div class="p-6 text-center text-on-surface-variant">No activity logged.</div>`;
      }
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function wireRoleDashboards() {
    if (PAGE.includes("doctor_dashboard")) {
      loadDoctorDashboard();
    } else if (PAGE.includes("admin_dashboard")) {
      loadAdminDashboard();
      
      // Admin verification queue click listener
      document.addEventListener("click", async (event) => {
        const btn = event.target.closest("[data-verify-doc]");
        if (btn) {
          event.preventDefault();
          const verifyId = btn.dataset.verifyDoc;
          const status = btn.dataset.verifyStatus;
          try {
            await api(`/admin/verify-doctor/${verifyId}`, {
              method: "POST",
              body: JSON.stringify({ status })
            });
            toast(`Doctor verification updated to: ${status}`);
            loadAdminDashboard();
          } catch (e) {
            toast(e.message, "error");
          }
        }
      });
    }
  }

  function injectGlobalAssistant() {
    if (PAGE.includes("unified_login_flow") || PAGE.includes("authentication_otp_flow") || !token()) return;
    
    // Check if assistant widget already exists
    if (document.getElementById("healthai-global-assistant-root")) return;

    // Create container
    const root = document.createElement("div");
    root.id = "healthai-global-assistant-root";
    root.className = "fixed bottom-24 lg:bottom-12 right-6 lg:right-10 z-[9999]";
    
    // Inject HTML
    root.innerHTML = `
      <!-- Floating Action Button -->
      <button id="global-assistant-fab" class="w-14 h-14 md:w-16 md:h-16 rounded-full bg-secondary text-on-secondary shadow-2xl flex items-center justify-center group hover:scale-110 active:scale-95 transition-all relative">
        <span class="material-symbols-outlined text-2xl md:text-3xl">smart_toy</span>
        <div class="absolute right-full mr-4 bg-inverse-surface text-inverse-on-surface px-4 py-2 rounded-xl text-label-md font-bold whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-md">
          Chat with HealthAI Assistant
        </div>
      </button>

      <!-- Chat Drawer/Widget -->
      <div id="global-assistant-drawer" class="hidden fixed bottom-6 right-6 w-96 max-w-[calc(100vw-48px)] h-[550px] bg-surface rounded-3xl shadow-2xl border border-outline-variant/30 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-300">
        <!-- Header -->
        <div class="p-md bg-primary text-white flex justify-between items-center shrink-0">
          <div class="flex items-center gap-sm">
            <span class="material-symbols-outlined text-secondary-fixed">smart_toy</span>
            <div>
              <p class="font-bold text-label-md">HealthAI Assistant</p>
              <p class="text-[10px] opacity-80">Online • English, Hindi, Telugu</p>
            </div>
          </div>
          <button id="global-assistant-close" class="material-symbols-outlined hover:text-secondary-fixed transition-colors">close</button>
        </div>
        
        <!-- Language selector chips -->
        <div class="px-md py-xs bg-surface-container flex gap-xs border-b border-outline-variant/20 text-xs text-on-surface-variant font-bold">
          <span>Language:</span>
          <button class="px-2 py-0.5 rounded-full bg-secondary text-on-secondary" onclick="window.setAssistantLanguage('en')">English</button>
          <button class="px-2 py-0.5 rounded-full bg-surface-container-high" onclick="window.setAssistantLanguage('hi')">हिन्दी</button>
          <button class="px-2 py-0.5 rounded-full bg-surface-container-high" onclick="window.setAssistantLanguage('te')">తెలుగు</button>
        </div>

        <!-- Chat Log -->
        <div id="global-assistant-log" class="flex-grow p-md overflow-y-auto space-y-md custom-scrollbar bg-surface-container-lowest">
          <div class="flex gap-sm max-w-[85%]">
            <div class="chat-bubble-ai p-md text-on-surface text-body-md bg-secondary/10 rounded-2xl">
              Hello! I am your HealthAI Global Assistant. I can help you search doctors, book appointments, check medical records, or analyze symptoms. Ask me anything in English, Hindi, or Telugu!
            </div>
          </div>
        </div>

        <!-- Input Box -->
        <div class="p-md border-t border-outline-variant/20 bg-surface shrink-0 flex gap-sm items-center">
          <input id="global-assistant-input" class="flex-1 px-md py-2 border border-outline-variant rounded-xl text-label-md focus:outline-none focus:border-secondary focus:ring-1 focus:ring-secondary" placeholder="Type a message..." type="text"/>
          <button id="global-assistant-send" class="w-10 h-10 rounded-xl bg-secondary text-on-secondary flex items-center justify-center hover:brightness-105 active:scale-95 transition-all">
            <span class="material-symbols-outlined">send</span>
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(root);

    // Setup interactive events
    const fab = document.getElementById("global-assistant-fab");
    const drawer = document.getElementById("global-assistant-drawer");
    const closeBtn = document.getElementById("global-assistant-close");
    const input = document.getElementById("global-assistant-input");
    const sendBtn = document.getElementById("global-assistant-send");
    const log = document.getElementById("global-assistant-log");

    // Hide original page specific chat-fab if it exists to avoid overlapping
    const pageFab = document.getElementById("chat-fab");
    if (pageFab) pageFab.classList.add("hidden");

    fab.addEventListener("click", () => {
      fab.classList.add("hidden");
      drawer.classList.remove("hidden");
      input.focus();
    });

    closeBtn.addEventListener("click", () => {
      drawer.classList.add("hidden");
      fab.classList.remove("hidden");
    });

    // Language selector state
    let activeLanguage = "en";
    window.setAssistantLanguage = (lang) => {
      activeLanguage = lang;
      // update chip buttons styling
      const buttons = drawer.querySelectorAll(".bg-secondary, .bg-surface-container-high");
      buttons.forEach(btn => {
        btn.className = "px-2 py-0.5 rounded-full bg-surface-container-high";
      });
      event.target.className = "px-2 py-0.5 rounded-full bg-secondary text-on-secondary";
      
      const welcome = {
        en: "How can I help you today?",
        hi: "मैं आज आपकी क्या सहायता कर सकता हूँ?",
        te: "నేను ఈ రోజు మీకు ఎలా సహాయపడగలను?"
      };
      appendMsg(welcome[lang], "ai");
    };

    function appendMsg(text, sender) {
      const bubble = document.createElement("div");
      bubble.className = sender === "user" ? "flex flex-col items-end gap-sm" : "flex gap-sm max-w-[85%]";
      const contentClass = sender === "user" ? "chat-bubble-user bg-surface-container-high text-on-surface border border-outline-variant" : "chat-bubble-ai bg-secondary/10 text-on-surface";
      bubble.innerHTML = `
        <div class="${contentClass} p-md text-body-md rounded-2xl">${text}</div>
      `;
      log.appendChild(bubble);
      log.scrollTop = log.scrollHeight;
    }

    async function handleSend() {
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      appendMsg(text, "user");

      // Show thinking bubble
      const thinking = document.createElement("div");
      thinking.id = "assistant-thinking-bubble";
      thinking.className = "flex gap-sm max-w-[85%]";
      thinking.innerHTML = `
        <div class="chat-bubble-ai bg-secondary/5 text-on-surface p-md rounded-2xl flex items-center gap-xs">
          <span class="animate-pulse">●</span><span class="animate-pulse delay-100">●</span><span class="animate-pulse delay-200">●</span>
        </div>
      `;
      log.appendChild(thinking);
      log.scrollTop = log.scrollHeight;

      try {
        const res = await api("/ai/assistant", {
          method: "POST",
          body: JSON.stringify({ message: text })
        });
        thinking.remove();
        appendMsg(res.reply, "ai");

        // Action Execution Router
        if (res.action) {
          executeAssistantAction(res.action);
        }

      } catch (err) {
        thinking.remove();
        appendMsg("Sorry, I encountered an error: " + err.message, "ai");
      }
    }

    sendBtn.addEventListener("click", handleSend);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        handleSend();
      }
    });

    async function executeAssistantAction(action) {
      appendMsg(`🔧 [Action: executing ${action.type.replace(/_/g, " ")}...]`, "ai");
      try {
        if (action.type === "find_doctors") {
          const spec = action.parameters.specialization || "";
          toast(`Searching for ${spec} specialist...`);
          if (PAGE.includes("doctor_search_booking")) {
            const searchInput = document.querySelector('input[placeholder*="Cardiologist"]');
            if (searchInput) {
              searchInput.value = spec;
              searchInput.dispatchEvent(new Event("input"));
            }
          } else {
            setTimeout(() => go(routes.appointments), 1500);
          }
        } 
        else if (action.type === "book_appointment") {
          const docId = action.parameters.doctor_id || 1;
          const date = action.parameters.date || new Date().toISOString().slice(0,10);
          const time = action.parameters.time || "10:30";
          
          toast(`Booking appointment for doctor ${docId} on ${date} at ${time}...`);
          
          await api("/appointment/book", {
            method: "POST",
            body: JSON.stringify({ doctor_id: docId, date, time })
          });
          
          toast("Appointment booked successfully!", "success");
          appendMsg(`📅 Confirmed! I have booked your appointment with the doctor for ${date} at ${time}.`, "ai");
          
          if (PAGE.includes("patient_dashboard")) {
            loadDashboard();
          }
        } 
        else if (action.type === "view_records") {
          toast("Opening medical records...");
          setTimeout(() => go(routes.records), 1000);
        } 
        else if (action.type === "view_dashboard") {
          toast("Navigating to home dashboard...");
          setTimeout(() => go(routes.dashboard), 1000);
        }
        else if (action.type === "analyze_symptom") {
          const symptoms = action.parameters.symptoms || "general check";
          const severity = action.parameters.severity || "moderate";
          const duration = action.parameters.duration || "1 day";
          
          toast("Analyzing symptoms...");
          const res = await api("/symptom/analyze", {
            method: "POST",
            body: JSON.stringify({ symptoms, severity, duration })
          });
          
          appendMsg(`📊 Symptom Assessment:\nRisk Category: ${res.symptom_log.risk_category}\nRecommendation: ${res.ai_recommendation || res.alert_message}`, "ai");
          
          if (PAGE.includes("patient_dashboard")) {
            loadDashboard();
          }
        }
      } catch (err) {
        appendMsg(`❌ Action execution failed: ${err.message}`, "ai");
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    window.__originalNextStep = window.nextStep;
    requireAuth();
    wireNavigation();
    wireLogin();
    wireAppointmentDelegates();
    loadDashboard();
    loadDoctors();
    wireSymptomChecker();
    wireRecordsAndChat();
    wireProfile();
    wireRoleDashboards();
    injectGlobalAssistant();
  });
})();
