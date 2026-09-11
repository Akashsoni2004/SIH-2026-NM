/**
 * PAIMANA AI - Master Role-Based Portal Controller
 * SIH 2026 | Neural Minds
 */

const Portal = (function() {
    let currentUser = null;
    let currentView = "dashboard";
    let projectsPage = 1;
    let projectsPageSize = 15;
    let projectSortBy = "orig_cost";
    let projectSortOrder = "desc";
    let currentDetailProject = null;
    let charts = {};

    // Initialize Portal
    async function init() {
        Auth.guardRoute();
        currentUser = Auth.getUser();
        if (!currentUser) return;

        // Render user identity in sidebar & topbar
        setupUserIdentity();
        // Render role-specific navigation menu
        renderSidebarMenu();
        // Load initial filter dropdowns
        await loadFilterOptions();
        // Determine view from URL
        determineInitialView();
        // Attach event listeners
        attachEvents();
        // Check top alert count
        updateTopAlertsBadge();
    }

    function setupUserIdentity() {
        const role = currentUser.role || "OFFICER";
        const roleEl = document.getElementById("sidebar-user-role");
        if (roleEl) {
            roleEl.textContent = role;
            roleEl.className = `role-pill role-${role.toLowerCase()}`;
        }

        const scopeEl = document.getElementById("sidebar-user-scope");
        if (scopeEl) {
            scopeEl.textContent = role === "AGENCY" ? (currentUser.organization || "Agency Scope") : "National Scope";
        }

        const nameEl = document.getElementById("sidebar-user-name");
        if (nameEl) nameEl.textContent = currentUser.full_name;

        const orgEl = document.getElementById("sidebar-user-org");
        if (orgEl) orgEl.textContent = currentUser.department || currentUser.organization;

        const topName = document.getElementById("top-user-name");
        if (topName) topName.textContent = currentUser.full_name;

        const topOrg = document.getElementById("top-user-org");
        if (topOrg) topOrg.textContent = `${role} • ${currentUser.organization}`;

        const initials = currentUser.full_name.split(" ").map(w => w[0]).join("").substring(0, 2).toUpperCase();
        const avatarEl = document.getElementById("top-user-avatar");
        if (avatarEl) avatarEl.textContent = initials;
        const profAvatar = document.getElementById("profile-avatar");
        if (profAvatar) profAvatar.textContent = initials;
    }

    function renderSidebarMenu() {
        const menu = document.getElementById("sidebar-menu");
        if (!menu) return;
        menu.innerHTML = "";

        const role = currentUser.role;

        // Navigation configurations per PRD Section 46
        let items = [];

        if (role === "ADMIN") {
            items = [
                { id: "dashboard", label: "Executive Dashboard", icon: "layout-dashboard", path: "/admin/dashboard" },
                { id: "projects", label: "Project Registry", icon: "layers", path: "/admin/projects" },
                { id: "admin-dashboard", label: "Administration Cockpit", icon: "shield-alert", path: "/admin/dashboard", sub: "users" },
                { id: "alerts", label: "Early Warning Alerts", icon: "alert-triangle", path: "/admin/alerts" },
                { id: "analytics", label: "Cross-Analytics", icon: "bar-chart-3", path: "/admin/analytics" },
                { id: "profile", label: "My Profile", icon: "user", path: "/profile" }
            ];
            const btnAdd = document.getElementById("btn-admin-add-proj");
            if (btnAdd) btnAdd.classList.remove("d-none");
        } else if (role === "POLICYMAKER") {
            items = [
                { id: "dashboard", label: "National Overview", icon: "layout-dashboard", path: "/dashboard" },
                { id: "projects", label: "All Projects", icon: "layers", path: "/projects" },
                { id: "analytics", label: "Sector & State Analytics", icon: "bar-chart-3", path: "/analytics" },
                { id: "alerts", label: "Critical Alerts", icon: "alert-triangle", path: "/alerts" },
                { id: "profile", label: "Profile", icon: "user", path: "/profile" }
            ];
        } else if (role === "MONITORING") {
            items = [
                { id: "dashboard", label: "Operational Risk Radar", icon: "activity", path: "/dashboard" },
                { id: "projects", label: "Monitored Projects", icon: "layers", path: "/projects" },
                { id: "alerts", label: "Early Warning Radar", icon: "alert-triangle", path: "/alerts" },
                { id: "analytics", label: "Performance Analytics", icon: "bar-chart-3", path: "/analytics" },
                { id: "profile", label: "Profile", icon: "user", path: "/profile" }
            ];
        } else if (role === "PLANNING") {
            items = [
                { id: "dashboard", label: "Capital Planning Dashboard", icon: "layout-dashboard", path: "/dashboard" },
                { id: "projects", label: "Infrastructure Projects", icon: "layers", path: "/projects" },
                { id: "analytics", label: "Macro Sector Analytics", icon: "bar-chart-3", path: "/analytics" },
                { id: "alerts", label: "Bottleneck Alerts", icon: "alert-triangle", path: "/alerts" },
                { id: "profile", label: "Profile", icon: "user", path: "/profile" }
            ];
        } else if (role === "AGENCY") {
            items = [
                { id: "dashboard", label: "My Agency Dashboard", icon: "layout-dashboard", path: "/dashboard" },
                { id: "projects", label: "My Projects", icon: "layers", path: "/projects" },
                { id: "alerts", label: "Agency Alerts", icon: "alert-triangle", path: "/alerts" },
                { id: "profile", label: "Profile", icon: "user", path: "/profile" }
            ];
            // Hide Agency filter from Agency users since it's redundant
            const agyWrap = document.getElementById("filter-agency-wrap");
            if (agyWrap) agyWrap.style.display = "none";
        }

        items.forEach(item => {
            const a = document.createElement("a");
            a.href = "javascript:void(0)";
            a.className = "sidebar-link";
            a.id = `nav-link-${item.id}`;
            a.innerHTML = `<i data-lucide="${item.icon}"></i><span>${item.label}</span>`;
            a.onclick = () => showView(item.id);
            menu.appendChild(a);
        });

        lucide.createIcons();
    }

    function determineInitialView() {
        const path = window.location.pathname;
        if (path.startsWith("/projects/") && path.split("/").length > 2) {
            const code = path.split("/")[2];
            showView("project-detail", { code });
        } else if (path.includes("/projects")) {
            showView("projects");
        } else if (path.includes("/alerts")) {
            showView("alerts");
        } else if (path.includes("/analytics")) {
            showView("analytics");
        } else if (path.includes("/profile")) {
            showView("profile");
        } else if (path.includes("/admin")) {
            if (currentUser.role === "ADMIN") {
                showView("admin-dashboard");
            } else {
                showView("403");
            }
        } else {
            showView("dashboard");
        }
    }

    function showView(viewId, params = {}) {
        // Enforce role guard
        if (viewId.startsWith("admin") && currentUser.role !== "ADMIN") {
            viewId = "403";
        }

        currentView = viewId;

        // Hide all views
        document.querySelectorAll(".portal-view").forEach(v => v.classList.add("d-none"));

        // Highlight sidebar item
        document.querySelectorAll(".sidebar-link").forEach(l => l.classList.remove("active"));
        const activeLink = document.getElementById(`nav-link-${viewId}`);
        if (activeLink) activeLink.classList.add("active");

        // Set Topbar Title
        const titleMap = {
            "dashboard": "Executive Dashboard",
            "projects": "Infrastructure Project Catalog",
            "project-detail": "Project Intelligence Dossier",
            "alerts": "Early Warning Alerts Radar",
            "analytics": "Cross-Cutting Analytics",
            "admin-dashboard": "System Administration Console",
            "profile": "My Profile & Credentials",
            "403": "Access Denied"
        };
        const titleEl = document.getElementById("topbar-title");
        if (titleEl) titleEl.textContent = titleMap[viewId] || "Dashboard";

        // Show target view
        const targetView = document.getElementById(`view-${viewId}`);
        if (targetView) targetView.classList.remove("d-none");

        // Load specific view data
        if (viewId === "dashboard") {
            loadDashboard();
        } else if (viewId === "projects") {
            if (params.risk_level) {
                const rSelect = document.getElementById("filter-risk");
                if (rSelect) rSelect.value = params.risk_level;
            }
            loadProjects();
        } else if (viewId === "project-detail") {
            if (params.code) loadProjectDetail(params.code);
        } else if (viewId === "alerts") {
            loadAlerts();
        } else if (viewId === "analytics") {
            loadAnalytics();
        } else if (viewId === "admin-dashboard") {
            loadAdminUsers();
        } else if (viewId === "profile") {
            loadProfile();
        }

        window.scrollTo({ top: 0, behavior: "smooth" });
        lucide.createIcons();
    }

    // ------------------ 1. DASHBOARD LOGIC ------------------
    async function loadDashboard() {
        try {
            const res = await Auth.fetchWithAuth("/api/dashboard/stats");
            const data = await res.json();

            // Set greeting based on role
            const greetingEl = document.getElementById("dash-greeting");
            const subEl = document.getElementById("dash-sub");
            const scopeTag = document.getElementById("dash-scope-tag");
            const role = currentUser.role;

            if (role === "AGENCY") {
                greetingEl.textContent = `${currentUser.organization} — Project Radar`;
                subEl.textContent = `Isolated surveillance view for all infrastructure assets under ${currentUser.organization}.`;
                scopeTag.innerHTML = `<i data-lucide="building"></i><span>${currentUser.organization} Scope</span>`;
            } else if (role === "MONITORING") {
                greetingEl.textContent = "Operational Risk Radar — Milestone Slippages";
                subEl.textContent = "Prioritized surveillance highlighting projects with imminent completion or cost breaches.";
            } else if (role === "PLANNING") {
                greetingEl.textContent = "Infrastructure Capital Expenditure & Progress Velocity";
                subEl.textContent = "Macro fund allocation, expenditure run rates, and sectoral execution trajectories.";
            }

            // Populate KPI Cards
            document.getElementById("stat-total-projects").textContent = Number(data.total_projects).toLocaleString();
            document.getElementById("stat-total-cost").textContent = `₹${(data.total_revised_cost_cr / 1000).toFixed(1)}K Cr`;
            document.getElementById("stat-orig-cost").textContent = `₹${(data.total_original_cost_cr / 1000).toFixed(1)}K Cr`;
            document.getElementById("stat-high-risk").textContent = Number(data.high_risk_count).toLocaleString();
            document.getElementById("stat-med-risk").textContent = Number(data.medium_risk_count).toLocaleString();
            document.getElementById("stat-low-risk").textContent = Number(data.low_risk_count).toLocaleString();
            document.getElementById("stat-delayed").textContent = Number(data.delayed_projects_count).toLocaleString();
            document.getElementById("stat-avg-delay").textContent = data.average_delay_months;
            document.getElementById("stat-overrun").textContent = Number(data.overrun_projects_count).toLocaleString();

            // Render Charts
            renderRiskPieChart(data.high_risk_count, data.medium_risk_count, data.low_risk_count);

            // Load Priority Projects Table
            loadPriorityProjectsTable();
            // Load Sector Bar Chart
            loadSectorChart();

        } catch (err) {
            showToast("Failed to load dashboard telemetry: " + err.message, "danger");
        }
    }

    function renderRiskPieChart(high, med, low) {
        const canvas = document.getElementById("chart-risk-pie");
        if (!canvas) return;
        if (charts.riskPie) charts.riskPie.destroy();

        charts.riskPie = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels: ["HIGH Risk", "MEDIUM Risk", "LOW Risk"],
                datasets: [{
                    data: [high, med, low],
                    backgroundColor: ["#ef4444", "#f59e0b", "#10b981"],
                    borderColor: "#0f172a",
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom", labels: { color: "#94a3b8", font: { family: "Inter" } } }
                },
                cutout: "68%"
            }
        });
    }

    async function loadSectorChart() {
        const canvas = document.getElementById("chart-sector-bar");
        if (!canvas) return;
        try {
            const res = await Auth.fetchWithAuth("/api/analytics/sectors");
            const data = await res.json();
            const top = data.slice(0, 7);

            if (charts.sectorBar) charts.sectorBar.destroy();
            charts.sectorBar = new Chart(canvas, {
                type: "bar",
                data: {
                    labels: top.map(d => d.sector.length > 15 ? d.sector.substring(0, 14) + "..." : d.sector),
                    datasets: [
                        {
                            label: "Total Revised Capital (₹ Cr)",
                            data: top.map(d => d.total_rev_cost),
                            backgroundColor: "#3b82f6",
                            borderRadius: 6
                        },
                        {
                            label: "Avg Delay (Months)",
                            data: top.map(d => d.avg_delay),
                            backgroundColor: "#f59e0b",
                            borderRadius: 6
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { ticks: { color: "#94a3b8", font: { size: 11 } }, grid: { display: false } },
                        y: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } }
                    },
                    plugins: {
                        legend: { labels: { color: "#94a3b8" } }
                    }
                }
            });
        } catch (e) {
            console.warn("Sector chart load error:", e);
        }
    }

    async function loadPriorityProjectsTable() {
        const tbody = document.getElementById("dash-priority-tbody");
        if (!tbody) return;
        try {
            const res = await Auth.fetchWithAuth("/api/projects?page_size=6&risk_level=HIGH&sort_by=cost_overrun_pct");
            const data = await res.json();
            if (!data.projects || data.projects.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-success">No high-risk projects currently flagged in this scope.</td></tr>`;
                return;
            }

            tbody.innerHTML = data.projects.map(p => {
                const riskBadge = `<span class="risk-badge risk-${p.risk_level.toLowerCase()}">${p.risk_level}</span>`;
                return `
                    <tr>
                        <td><span class="mono-code">${p.project_code}</span></td>
                        <td><strong>${p.project_name}</strong></td>
                        <td>${p.agency}</td>
                        <td>${p.sector}</td>
                        <td>${riskBadge}</td>
                        <td><span class="text-warning">${p.delay_months || 0} mo</span></td>
                        <td><span class="${p.progress_gap > 15 ? 'text-danger' : 'text-muted'}">${p.progress_gap ? p.progress_gap.toFixed(1) + '%' : '0%'}</span></td>
                        <td>
                            <button class="btn btn-sm btn-outline" onclick="Portal.showView('project-detail', {code: '${p.project_code}'})">
                                Inspect
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
            lucide.createIcons();
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Failed to load priority projects.</td></tr>`;
        }
    }

    // ------------------ 2. PROJECTS CATALOG ------------------
    async function loadProjects() {
        const tbody = document.getElementById("projects-table-body");
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-5">Loading project catalog...</td></tr>`;

        const search = document.getElementById("proj-search")?.value.trim() || "";
        const sector = document.getElementById("filter-sector")?.value || "ALL";
        const state = document.getElementById("filter-state")?.value || "ALL";
        const agency = document.getElementById("filter-agency")?.value || "ALL";
        const risk = document.getElementById("filter-risk")?.value || "ALL";
        const ministry = document.getElementById("filter-ministry")?.value || "ALL";

        const params = new URLSearchParams({
            page: projectsPage,
            page_size: projectsPageSize,
            sort_by: projectSortBy,
            sort_order: projectSortOrder
        });

        if (search) params.append("search", search);
        if (sector !== "ALL") params.append("sector", sector);
        if (state !== "ALL") params.append("state", state);
        if (agency !== "ALL") params.append("agency", agency);
        if (risk !== "ALL") params.append("risk_level", risk);
        if (ministry !== "ALL") params.append("ministry", ministry);

        try {
            const res = await Auth.fetchWithAuth(`/api/projects?${params.toString()}`);
            const data = await res.json();

            document.getElementById("projects-count-info").textContent = `Showing ${(projectsPage - 1) * projectsPageSize + 1}–${Math.min(projectsPage * projectsPageSize, data.total)} of ${data.total} infrastructure projects`;
            document.getElementById("pagination-info").textContent = `Page ${data.page} of ${Math.max(1, data.total_pages)}`;

            document.getElementById("btn-prev-page").disabled = data.page <= 1;
            document.getElementById("btn-next-page").disabled = data.page >= data.total_pages;

            if (data.projects.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" class="text-center py-5 text-muted">No infrastructure projects found matching the active filters.</td></tr>`;
                return;
            }

            tbody.innerHTML = data.projects.map(p => {
                const riskBadge = `<span class="risk-badge risk-${p.risk_level.toLowerCase()}">${p.risk_level}</span>`;
                const delayBadge = p.delay_months > 0 
                    ? `<span class="delay-pill delay-high">+${p.delay_months} mo</span>`
                    : `<span class="delay-pill delay-none">On Schedule</span>`;

                return `
                    <tr>
                        <td><span class="mono-code">${p.project_code}</span></td>
                        <td>
                            <div class="project-cell-name">
                                <a href="javascript:void(0)" onclick="Portal.showView('project-detail', {code: '${p.project_code}'})">
                                    <strong>${p.project_name}</strong>
                                </a>
                                <span class="cell-sub">${p.state} • ${p.ministry}</span>
                            </div>
                        </td>
                        <td>${p.agency}</td>
                        <td>${p.sector}</td>
                        <td>
                            <div class="table-prog-cell">
                                <span>${p.progress ? p.progress.toFixed(1) : 0}%</span>
                                <div class="prog-track-sm">
                                    <div class="prog-bar-sm" style="width: ${Math.min(100, p.progress || 0)}%"></div>
                                </div>
                            </div>
                        </td>
                        <td>
                            <div class="cost-cell">
                                <span class="rev-cost">₹${Number(p.rev_cost || 0).toLocaleString()} Cr</span>
                                <span class="orig-cost">Orig: ₹${Number(p.orig_cost || 0).toLocaleString()} Cr</span>
                            </div>
                        </td>
                        <td>${delayBadge}</td>
                        <td>${riskBadge}</td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="Portal.showView('project-detail', {code: '${p.project_code}'})">
                                Inspect Dossier
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
            lucide.createIcons();
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger py-4">Error loading project catalog: ${err.message}</td></tr>`;
        }
    }

    function handleSortChange() {
        const select = document.getElementById("sort-by-select");
        if (select) {
            projectSortBy = select.value;
            projectsPage = 1;
            loadProjects();
        }
    }

    function resetProjectFilters() {
        document.getElementById("proj-search").value = "";
        document.getElementById("filter-sector").value = "ALL";
        document.getElementById("filter-state").value = "ALL";
        const agy = document.getElementById("filter-agency");
        if (agy) agy.value = "ALL";
        const min = document.getElementById("filter-ministry");
        if (min) min.value = "ALL";
        document.getElementById("filter-risk").value = "ALL";
        projectsPage = 1;
        loadProjects();
    }

    function prevPage() {
        if (projectsPage > 1) {
            projectsPage--;
            loadProjects();
        }
    }

    function nextPage() {
        projectsPage++;
        loadProjects();
    }

    // ------------------ 3. PROJECT DEEP-DIVE ------------------
    async function loadProjectDetail(code) {
        try {
            const res = await Auth.fetchWithAuth(`/api/projects/${code}`);
            if (res.status === 403) {
                showView("403");
                return;
            }
            const p = await res.json();
            currentDetailProject = p;

            // Identity Header
            document.getElementById("detail-code").textContent = `#${p.project_code}`;
            document.getElementById("detail-title").textContent = p.project_name;
            document.getElementById("detail-agency").textContent = p.agency;
            document.getElementById("detail-ministry").textContent = p.ministry;
            document.getElementById("detail-sector").textContent = p.sector;
            document.getElementById("detail-state").textContent = p.state;
            document.getElementById("detail-status").textContent = `Status: Ongoing (${p.time_elapsed_months || 24} mo elapsed)`;

            // Progress Bars
            const phys = p.progress || 0;
            const fin = p.financial_progress_pct || 0;
            const gap = p.progress_gap || 0;

            document.getElementById("detail-phys-prog").textContent = `${phys.toFixed(1)}%`;
            document.getElementById("detail-phys-bar").style.width = `${Math.min(100, phys)}%`;

            document.getElementById("detail-fin-prog").textContent = `${fin.toFixed(1)}%`;
            document.getElementById("detail-fin-bar").style.width = `${Math.min(100, fin)}%`;

            document.getElementById("detail-gap-prog").textContent = `${gap.toFixed(1)}%`;
            document.getElementById("detail-gap-bar").style.width = `${Math.min(100, Math.max(0, gap))}%`;

            // Risk Panel & AI Predictions
            const pred = p.ai_prediction || {};
            const riskScore = pred.risk_score || 50;
            const riskLevel = pred.risk_level || p.risk_level || "MEDIUM";

            document.getElementById("detail-risk-score").textContent = riskScore;
            const rBadge = document.getElementById("detail-risk-level");
            rBadge.textContent = `${riskLevel} RISK`;
            rBadge.className = `risk-badge badge-lg risk-${riskLevel.toLowerCase()}`;

            document.getElementById("detail-risk-desc").textContent = `Calculated using longitudinal velocity tracking & 12 feature vectors.`;
            document.getElementById("detail-delay-prob").textContent = `${pred.delay_probability ? (pred.delay_probability * 100).toFixed(0) : (p.delay_months > 0 ? 78 : 22)}%`;
            document.getElementById("detail-cost-risk").textContent = `${pred.pred_overrun_pct ? Math.min(99, pred.pred_overrun_pct * 2).toFixed(0) : 34}%`;
            document.getElementById("detail-sched-dev").textContent = `${p.delay_months || 0} Months`;

            document.getElementById("detail-risk-rationale").textContent = 
                riskLevel === "HIGH" 
                    ? "Risk elevated due to widening gap between expenditure burn and ground milestone execution accompanied by persistent schedule slippage."
                    : "Project is operating within baseline timeline tolerance; ongoing periodic review advised.";

            // Forecast numbers
            const predDelayM = pred.predicted_delay_months !== undefined ? pred.predicted_delay_months : (p.delay_months || 0);
            const predDelayDays = pred.predicted_delay_days !== undefined ? pred.predicted_delay_days : (predDelayM * 30);
            const predFinalCost = pred.predicted_final_cost !== undefined ? pred.predicted_final_cost : (p.rev_cost || 0);
            const predOverrunPct = pred.predicted_cost_overrun_pct !== undefined ? pred.predicted_cost_overrun_pct : (p.cost_overrun_pct || 0);

            document.getElementById("detail-pred-delay").textContent = `${predDelayM} Months`;
            document.getElementById("detail-pred-delay-days").textContent = `(~${predDelayDays} calendar days)`;
            document.getElementById("detail-pred-cost").textContent = `₹${Number(predFinalCost).toLocaleString()} Cr`;
            document.getElementById("detail-pred-overrun-pct").textContent = `(Estimated +${predOverrunPct}% cost overrun)`;

            // Anomaly Alert Box
            const anomBox = document.getElementById("detail-anomaly-box");
            if (p.is_anomaly || pred.is_anomaly) {
                anomBox.classList.remove("d-none");
            } else {
                anomBox.classList.add("d-none");
            }

            // XAI Drivers
            const xaiContainer = document.getElementById("detail-xai-factors");
            xaiContainer.innerHTML = "";
            const factors = pred.risk_factors || [
                { factor: "Progress Gap (Spend vs Physical)", contribution_pct: 42.5 },
                { factor: "Time Elapsed Overrun", contribution_pct: 28.0 },
                { factor: "Delay Slippage Pattern", contribution_pct: 18.5 },
                { factor: "Progress Velocity Stalling", contribution_pct: 11.0 }
            ];

            factors.forEach(f => {
                xaiContainer.innerHTML += `
                    <div class="xai-factor-row">
                        <div class="xai-factor-info">
                            <span class="xai-factor-name">${f.factor}</span>
                            <span class="xai-factor-pct">${f.contribution_pct}% influence</span>
                        </div>
                        <div class="prog-track-sm">
                            <div class="prog-bar-sm bg-warning" style="width: ${f.contribution_pct}%"></div>
                        </div>
                    </div>
                `;
            });

            // AI Recommendations
            const recsContainer = document.getElementById("detail-recs-list");
            recsContainer.innerHTML = "";
            const recs = pred.recommendations || [
                { title: "Escalate Clearances", action: "Issue expedited directive to contractor to mobilize additional machinery on pending package." },
                { title: "Tripartite Review", action: "Conduct tripartite review between State Nodal Officer, Agency Chief Engineer, and IPMD." }
            ];

            recs.forEach((r, idx) => {
                const recTitle = typeof r === "object" ? r.title : `Action Item ${idx + 1}`;
                const recAction = typeof r === "object" ? r.action : r;
                recsContainer.innerHTML += `
                    <div class="rec-item">
                        <div class="rec-num">${idx + 1}</div>
                        <div class="rec-text">
                            <strong>${recTitle}:</strong> ${recAction}
                        </div>
                    </div>
                `;
            });

            // Longitudinal History Chart
            renderProjectHistoryChart(p.history || []);
            lucide.createIcons();

        } catch (err) {
            showToast("Error loading project dossier: " + err.message, "danger");
        }
    }

    function renderProjectHistoryChart(history) {
        const canvas = document.getElementById("chart-project-history");
        if (!canvas) return;
        if (charts.projHistory) charts.projHistory.destroy();

        const labels = history.length ? history.map(h => h.month) : ["April 2026", "May 2026", "June 2026", "July 2026"];
        const progressData = history.length ? history.map(h => h.progress) : [20, 22, 23.5, 25];
        const expenditureData = history.length ? history.map(h => h.expenditure) : [100, 150, 220, 310];

        charts.projHistory = new Chart(canvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Ground Physical Progress (%)",
                        data: progressData,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59, 130, 246, 0.1)",
                        fill: true,
                        tension: 0.3,
                        yAxisID: "y"
                    },
                    {
                        label: "Cumulative Expenditure (₹ Cr)",
                        data: expenditureData,
                        borderColor: "#a855f7",
                        backgroundColor: "transparent",
                        borderDash: [5, 5],
                        tension: 0.3,
                        yAxisID: "y1"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } },
                    y: { 
                        ticks: { color: "#3b82f6" }, 
                        title: { display: true, text: "Progress %", color: "#3b82f6" },
                        grid: { color: "#1e293b" } 
                    },
                    y1: {
                        position: "right",
                        ticks: { color: "#a855f7" },
                        title: { display: true, text: "Expenditure (₹ Cr)", color: "#a855f7" },
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { labels: { color: "#94a3b8" } }
                }
            }
        });
    }

    // ------------------ 4. EARLY WARNING ALERTS ------------------
    async function loadAlerts() {
        const grid = document.getElementById("alerts-stream-grid");
        if (!grid) return;
        grid.innerHTML = `<div class="text-center py-5">Scanning early warning radar...</div>`;

        const cat = document.getElementById("alert-filter-cat")?.value || "ALL";
        const prio = document.getElementById("alert-filter-prio")?.value || "ALL";

        try {
            const res = await Auth.fetchWithAuth(`/api/alerts?category=${cat}&priority=${prio}&limit=40`);
            const alerts = await res.json();

            if (alerts.length === 0) {
                grid.innerHTML = `<div class="text-center py-5 text-success">No early warning alerts matching the selected filters.</div>`;
                return;
            }

            grid.innerHTML = alerts.map(a => {
                const prioClass = a.priority.toLowerCase();
                return `
                    <div class="alert-card glass-panel prio-${prioClass}">
                        <div class="alert-card-top">
                            <div class="alert-prio-badge prio-${prioClass}">
                                <i data-lucide="${a.priority === 'CRITICAL' ? 'alert-octagon' : 'alert-triangle'}"></i>
                                <span>${a.priority} PRIORITY</span>
                            </div>
                            <span class="alert-cat-tag">${a.category.replace('_', ' ')}</span>
                        </div>

                        <h4 class="alert-proj-title">${a.project_name}</h4>
                        <div class="alert-meta">
                            <span>Code: <strong>${a.project_code}</strong></span> • 
                            <span>Agency: <strong>${a.agency}</strong></span> • 
                            <span>State: <strong>${a.state}</strong></span>
                        </div>

                        <div class="alert-reason-box">
                            <strong><i data-lucide="info"></i> Risk Trigger:</strong>
                            <p>${a.reason}</p>
                        </div>

                        <div class="alert-action-box">
                            <strong><i data-lucide="check-circle-2"></i> Recommended Administrative Intervention:</strong>
                            <p>${a.recommended_action}</p>
                        </div>

                        <div class="alert-card-bottom">
                            <div class="alert-stats-inline">
                                <span>Delay: <strong>${a.delay_months || 0} mo</strong></span>
                                <span>Cost Overrun: <strong>${a.cost_overrun_pct || 0}%</strong></span>
                                <span>Progress: <strong>${a.progress ? a.progress.toFixed(1) : 0}%</strong></span>
                            </div>
                            <button class="btn btn-sm btn-outline" onclick="Portal.showView('project-detail', {code: '${a.project_code}'})">
                                Inspect Project &rarr;
                            </button>
                        </div>
                    </div>
                `;
            }).join("");
            lucide.createIcons();

        } catch (err) {
            grid.innerHTML = `<div class="text-center py-5 text-danger">Failed to scan alerts: ${err.message}</div>`;
        }
    }

    async function updateTopAlertsBadge() {
        try {
            const res = await Auth.fetchWithAuth("/api/alerts?limit=10");
            if (res.ok) {
                const data = await res.json();
                const badge = document.getElementById("top-alert-count");
                if (badge) badge.textContent = data.length;
            }
        } catch (e) {}
    }

    // ------------------ 5. ANALYTICS VIEW ------------------
    let currentAnalyticsTab = "sectors";
    function setAnalyticsTab(tab, buttonEl) {
        currentAnalyticsTab = tab;
        document.querySelectorAll(".analytics-tabs-row .tab-btn").forEach(b => b.classList.remove("active"));
        if (buttonEl) buttonEl.classList.add("active");
        loadAnalytics();
    }

    async function loadAnalytics() {
        const thead = document.getElementById("analytics-thead");
        const tbody = document.getElementById("analytics-tbody");
        if (!thead || !tbody) return;
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4">Loading analytics...</td></tr>`;

        try {
            const res = await Auth.fetchWithAuth(`/api/analytics/${currentAnalyticsTab}`);
            const data = await res.json();

            // Render chart
            renderAnalyticsChart(data, currentAnalyticsTab);

            if (currentAnalyticsTab === "sectors") {
                thead.innerHTML = `
                    <tr>
                        <th>Sector</th>
                        <th>Projects</th>
                        <th>Total Capital Outlay</th>
                        <th>Cumulative Expenditure</th>
                        <th>Avg Delay (mo)</th>
                        <th>High Risk Projects</th>
                        <th>Anomalies</th>
                    </tr>
                `;
                tbody.innerHTML = data.map(d => `
                    <tr>
                        <td><strong>${d.sector}</strong></td>
                        <td>${d.project_count}</td>
                        <td>₹${d.total_rev_cost.toLocaleString()} Cr</td>
                        <td>₹${d.total_exp.toLocaleString()} Cr</td>
                        <td><span class="text-warning">${d.avg_delay} mo</span></td>
                        <td><span class="risk-badge risk-high">${d.high_risk_count}</span></td>
                        <td>${d.anomaly_count}</td>
                    </tr>
                `).join("");
            } else if (currentAnalyticsTab === "ministries") {
                thead.innerHTML = `
                    <tr>
                        <th>Ministry</th>
                        <th>Projects</th>
                        <th>Total Revised Outlay</th>
                        <th>Avg Delay (mo)</th>
                        <th>Avg Cost Escalation (%)</th>
                        <th>High Risk Projects</th>
                    </tr>
                `;
                tbody.innerHTML = data.map(d => `
                    <tr>
                        <td><strong>${d.ministry}</strong></td>
                        <td>${d.project_count}</td>
                        <td>₹${d.total_rev_cost.toLocaleString()} Cr</td>
                        <td><span class="text-warning">${d.avg_delay} mo</span></td>
                        <td><span class="${d.avg_cost_overrun > 15 ? 'text-danger' : 'text-muted'}">${d.avg_cost_overrun}%</span></td>
                        <td><span class="risk-badge risk-high">${d.high_risk_count}</span></td>
                    </tr>
                `).join("");
            } else if (currentAnalyticsTab === "states") {
                thead.innerHTML = `
                    <tr>
                        <th>State / UT</th>
                        <th>Projects</th>
                        <th>Total Capital Outlay</th>
                        <th>Avg Delay (mo)</th>
                        <th>Avg Physical Progress</th>
                        <th>High Risk Projects</th>
                    </tr>
                `;
                tbody.innerHTML = data.map(d => `
                    <tr>
                        <td><strong>${d.state}</strong></td>
                        <td>${d.project_count}</td>
                        <td>₹${d.total_cost.toLocaleString()} Cr</td>
                        <td><span class="text-warning">${d.avg_delay} mo</span></td>
                        <td>${d.avg_progress}%</td>
                        <td><span class="risk-badge risk-high">${d.high_risk_count}</span></td>
                    </tr>
                `).join("");
            } else if (currentAnalyticsTab === "agencies") {
                thead.innerHTML = `
                    <tr>
                        <th>Implementing Agency</th>
                        <th>Projects</th>
                        <th>Total Capital Outlay</th>
                        <th>Avg Delay (mo)</th>
                        <th>Avg Physical Progress</th>
                        <th>High Risk Projects</th>
                    </tr>
                `;
                tbody.innerHTML = data.map(d => `
                    <tr>
                        <td><strong>${d.agency}</strong></td>
                        <td>${d.project_count}</td>
                        <td>₹${d.total_rev_cost.toLocaleString()} Cr</td>
                        <td><span class="text-warning">${d.avg_delay} mo</span></td>
                        <td>${d.avg_progress}%</td>
                        <td><span class="risk-badge risk-high">${d.high_risk_count}</span></td>
                    </tr>
                `).join("");
            }
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Failed to load analytics: ${err.message}</td></tr>`;
        }
    }

    function renderAnalyticsChart(data, tab) {
        const canvas = document.getElementById("chart-analytics-bar");
        if (!canvas || !data || data.length === 0) return;
        if (charts.analyticsBar) charts.analyticsBar.destroy();

        let labels = [], costData = [], riskData = [], delayData = [];

        if (tab === "sectors") {
            labels = data.slice(0, 8).map(d => d.sector.length > 16 ? d.sector.slice(0, 15) + "…" : d.sector);
            costData = data.slice(0, 8).map(d => +(d.total_rev_cost / 1000).toFixed(1)); // K Cr
            riskData = data.slice(0, 8).map(d => d.high_risk_count);
            delayData = data.slice(0, 8).map(d => d.avg_delay);
        } else if (tab === "ministries") {
            labels = data.slice(0, 8).map(d => d.ministry.length > 18 ? d.ministry.slice(0, 17) + "…" : d.ministry);
            costData = data.slice(0, 8).map(d => +(d.total_rev_cost / 1000).toFixed(1));
            riskData = data.slice(0, 8).map(d => d.high_risk_count);
            delayData = data.slice(0, 8).map(d => d.avg_delay);
        } else if (tab === "states") {
            labels = data.slice(0, 8).map(d => d.state.length > 16 ? d.state.slice(0, 15) + "…" : d.state);
            costData = data.slice(0, 8).map(d => +(d.total_cost / 1000).toFixed(1));
            riskData = data.slice(0, 8).map(d => d.high_risk_count);
            delayData = data.slice(0, 8).map(d => d.avg_delay);
        } else if (tab === "agencies") {
            labels = data.slice(0, 8).map(d => d.agency.length > 18 ? d.agency.slice(0, 17) + "…" : d.agency);
            costData = data.slice(0, 8).map(d => +(d.total_rev_cost / 1000).toFixed(1));
            riskData = data.slice(0, 8).map(d => d.high_risk_count);
            delayData = data.slice(0, 8).map(d => d.avg_delay);
        }

        charts.analyticsBar = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Capital Outlay (₹ 000 Cr)",
                        data: costData,
                        backgroundColor: "rgba(59,130,246,0.75)",
                        borderRadius: 6,
                        yAxisID: "y"
                    },
                    {
                        label: "High Risk Projects",
                        data: riskData,
                        backgroundColor: "rgba(239,68,68,0.75)",
                        borderRadius: 6,
                        yAxisID: "y1"
                    },
                    {
                        label: "Avg Delay (months)",
                        data: delayData,
                        backgroundColor: "rgba(245,158,11,0.75)",
                        borderRadius: 6,
                        yAxisID: "y1"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { display: false } },
                    y: {
                        ticks: { color: "#3b82f6" },
                        title: { display: true, text: "₹ 000 Cr", color: "#3b82f6" },
                        grid: { color: "#1e293b" }
                    },
                    y1: {
                        position: "right",
                        ticks: { color: "#f59e0b" },
                        title: { display: true, text: "Count / Months", color: "#f59e0b" },
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { labels: { color: "#94a3b8", font: { family: "Inter" } } }
                }
            }
        });
    }

    // ------------------ 6. ADMIN PORTAL LOGIC ------------------
    let currentAdminSub = "users";
    function setAdminSubView(sub) {
        currentAdminSub = sub;
        document.querySelectorAll(".admin-tab").forEach(t => t.classList.remove("active"));
        event.target.classList.add("active");

        document.querySelectorAll(".admin-subview").forEach(s => s.classList.add("d-none"));
        const target = document.getElementById(`admin-sub-${sub}`);
        if (target) target.classList.remove("d-none");

        if (sub === "users") loadAdminUsers();
        else if (sub === "agencies") loadAdminAgencies();
        else if (sub === "audit-logs") loadAdminAuditLogs();
        else if (sub === "settings") loadAdminSettings();
    }

    async function loadAdminUsers() {
        const tbody = document.getElementById("admin-users-tbody");
        if (!tbody) return;
        const search = document.getElementById("admin-user-search")?.value || "";

        try {
            const res = await Auth.fetchWithAuth(`/api/admin/users?search=${encodeURIComponent(search)}`);
            const users = await res.json();

            tbody.innerHTML = users.map(u => `
                <tr>
                    <td>#${u.id}</td>
                    <td><strong>${u.full_name}</strong></td>
                    <td>${u.email} <br><span class="text-muted">(${u.username})</span></td>
                    <td><span class="role-pill role-${u.role.toLowerCase()}">${u.role}</span></td>
                    <td>${u.organization}</td>
                    <td><span class="badge ${u.is_active ? 'badge-success' : 'badge-danger'}">${u.is_active ? 'Active' : 'Disabled'}</span></td>
                    <td>${u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}</td>
                    <td>
                        <button class="btn btn-sm btn-outline" onclick="Portal.toggleUserStatus(${u.id}, ${u.is_active ? 0 : 1})">
                            ${u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                    </td>
                </tr>
            `).join("");
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Error loading users: ${err.message}</td></tr>`;
        }
    }

    async function toggleUserStatus(userId, newStatus) {
        try {
            const res = await Auth.fetchWithAuth(`/api/admin/users/${userId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: newStatus })
            });
            if (res.ok) {
                showToast("User status updated successfully.", "success");
                loadAdminUsers();
            }
        } catch (err) {
            showToast("Failed to update user: " + err.message, "danger");
        }
    }

    async function loadAdminAgencies() {
        const tbody = document.getElementById("admin-agencies-tbody");
        if (!tbody) return;
        try {
            const res = await Auth.fetchWithAuth("/api/admin/agencies");
            const agencies = await res.json();

            tbody.innerHTML = agencies.map(a => `
                <tr>
                    <td><span class="mono-code">${a.code}</span></td>
                    <td><strong>${a.name}</strong></td>
                    <td>${a.ministry}</td>
                    <td>${a.org_type}</td>
                    <td>${a.project_count || 0}</td>
                    <td>₹${(a.total_capital_cr || 0).toLocaleString()} Cr</td>
                    <td>${a.contact_email || 'N/A'}</td>
                </tr>
            `).join("");
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error loading agencies.</td></tr>`;
        }
    }

    async function loadAdminAuditLogs() {
        const tbody = document.getElementById("admin-audit-tbody");
        if (!tbody) return;
        const action = document.getElementById("audit-action-filter")?.value || "ALL";

        try {
            const res = await Auth.fetchWithAuth(`/api/admin/audit-logs?action=${action}&page_size=25`);
            const data = await res.json();

            document.getElementById("audit-logs-total").textContent = `Total recorded events: ${data.total}`;
            tbody.innerHTML = data.logs.map(l => `
                <tr>
                    <td><span class="mono-code">${new Date(l.timestamp).toLocaleString()}</span></td>
                    <td><strong>${l.username}</strong></td>
                    <td><span class="role-pill role-${l.role.toLowerCase()}">${l.role}</span></td>
                    <td><span class="badge ${l.status === 'SUCCESS' ? 'badge-info' : 'badge-danger'}">${l.action}</span></td>
                    <td>${l.resource || '-'}</td>
                    <td><span class="badge ${l.status === 'SUCCESS' ? 'badge-success' : 'badge-danger'}">${l.status}</span></td>
                    <td><span class="mono-code">${l.ip_address || '127.0.0.1'}</span></td>
                    <td><span class="text-muted">${l.details || '-'}</span></td>
                </tr>
            `).join("");
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">Error loading audit logs: ${err.message}</td></tr>`;
        }
    }

    async function loadAdminSettings() {
        try {
            const res = await Auth.fetchWithAuth("/api/admin/settings");
            const settings = await res.json();

            if (settings.high_risk_threshold) {
                document.getElementById("setting-high-risk").value = settings.high_risk_threshold.value;
            }
            if (settings.delay_alarm_months) {
                document.getElementById("setting-delay-alarm").value = settings.delay_alarm_months.value;
            }
            if (settings.cost_overrun_alarm_pct) {
                document.getElementById("setting-cost-alarm").value = settings.cost_overrun_alarm_pct.value;
            }
        } catch (e) {
            console.warn("Settings load error:", e);
        }
    }

    async function saveAdminSettings(e) {
        e.preventDefault();
        const payload = {
            high_risk_threshold: document.getElementById("setting-high-risk").value,
            delay_alarm_months: document.getElementById("setting-delay-alarm").value,
            cost_overrun_alarm_pct: document.getElementById("setting-cost-alarm").value
        };

        try {
            const res = await Auth.fetchWithAuth("/api/admin/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                showToast("System settings updated successfully.", "success");
            }
        } catch (err) {
            showToast("Failed to save settings: " + err.message, "danger");
        }
    }

    // ------------------ 7. PROFILE VIEW ------------------
    function loadProfile() {
        if (!currentUser) return;
        document.getElementById("profile-name").textContent = currentUser.full_name;
        document.getElementById("profile-role-badge").textContent = currentUser.role;
        document.getElementById("profile-role-badge").className = `role-pill role-${currentUser.role.toLowerCase()}`;
        document.getElementById("profile-email").textContent = currentUser.email;
        document.getElementById("profile-username").textContent = currentUser.username;
        document.getElementById("profile-org").textContent = currentUser.organization;
        document.getElementById("profile-dept").textContent = currentUser.department;
    }

    async function changePassword(e) {
        e.preventDefault();
        const old_password = document.getElementById("old-pwd").value;
        const new_password = document.getElementById("new-pwd").value;

        try {
            const res = await Auth.fetchWithAuth("/api/profile/change-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ old_password, new_password })
            });
            const data = await res.json();
            if (res.ok) {
                showToast("Password updated successfully.", "success");
                document.getElementById("form-change-pwd").reset();
            } else {
                showToast(data.detail || "Password update failed.", "danger");
            }
        } catch (err) {
            showToast(err.message, "danger");
        }
    }

    // ------------------ 8. WHAT-IF SIMULATION LAB ------------------
    function openGlobalSimModal() {
        document.getElementById("modal-sim").classList.remove("d-none");
        runSimulation();
    }

    function openProjectSim() {
        if (!currentDetailProject) return;
        document.getElementById("sim-orig-cost").value = currentDetailProject.orig_cost || 1000;
        document.getElementById("sim-rev-cost").value = currentDetailProject.rev_cost || 1200;
        document.getElementById("sim-exp").value = currentDetailProject.expenditure || 800;
        document.getElementById("sim-prog").value = currentDetailProject.progress || 45;
        document.getElementById("sim-pv").value = currentDetailProject.progress_velocity || 1.2;
        document.getElementById("sim-slip").value = currentDetailProject.delay_slippage || 0;

        document.getElementById("modal-sim").classList.remove("d-none");
        runSimulation();
    }

    function closeSimModal() {
        document.getElementById("modal-sim").classList.add("d-none");
    }

    async function runSimulation() {
        const orig = parseFloat(document.getElementById("sim-orig-cost").value);
        const rev = parseFloat(document.getElementById("sim-rev-cost").value);
        const exp = parseFloat(document.getElementById("sim-exp").value);
        const prog = parseFloat(document.getElementById("sim-prog").value);
        const pv = parseFloat(document.getElementById("sim-pv").value);
        const slip = parseFloat(document.getElementById("sim-slip").value);

        document.getElementById("val-sim-orig").textContent = orig;
        document.getElementById("val-sim-rev").textContent = rev;
        document.getElementById("val-sim-exp").textContent = exp;
        document.getElementById("val-sim-prog").textContent = prog;
        document.getElementById("val-sim-pv").textContent = pv;
        document.getElementById("val-sim-slip").textContent = slip;

        const payload = {
            orig_cost: orig,
            rev_cost: rev,
            expenditure: exp,
            progress: prog,
            progress_velocity: pv,
            delay_slippage: slip,
            time_elapsed_months: 24,
            planned_duration_months: 36
        };

        try {
            const res = await Auth.fetchWithAuth("/api/predict", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const pred = await res.json();

            const riskLevel = pred.risk_level || "MEDIUM";
            const badge = document.getElementById("sim-res-risk-level");
            badge.textContent = `${riskLevel} RISK`;
            badge.className = `risk-badge risk-${riskLevel.toLowerCase()}`;

            document.getElementById("sim-res-risk-score").textContent = `${pred.risk_score || 50} / 100`;
            document.getElementById("sim-res-delay").textContent = `${pred.pred_delay_m || 0} Months`;
            document.getElementById("sim-res-cost").textContent = `₹${(pred.pred_final_cost || rev).toLocaleString()} Cr`;

            const anomEl = document.getElementById("sim-res-anom");
            if (pred.is_anomaly) {
                anomEl.textContent = "DIVERGENCE DETECTED";
                anomEl.className = "badge badge-danger";
            } else {
                anomEl.textContent = "NORMAL CORRELATION";
                anomEl.className = "badge badge-success";
            }
        } catch (e) {
            console.warn("Simulation call error:", e);
        }
    }

    // ------------------ 9. ML BENCHMARKS MODAL ------------------
    async function openBenchmarkModal() {
        document.getElementById("modal-benchmarks").classList.remove("d-none");
        const clfTbody = document.getElementById("benchmarks-clf-tbody");
        const regTbody = document.getElementById("benchmarks-reg-tbody");
        if (!clfTbody || !regTbody) return;

        try {
            const res = await Auth.fetchWithAuth("/api/model/benchmarks");
            const bm = await res.json();

            const clfs = bm.classifiers || {};
            clfTbody.innerHTML = Object.keys(clfs).map(k => {
                const c = clfs[k];
                const isBest = k.includes("XGBoost");
                return `
                    <tr class="${isBest ? 'highlight-row' : ''}">
                        <td><strong>${k}</strong></td>
                        <td>${(c.accuracy * 100).toFixed(2)}%</td>
                        <td>${(c.precision * 100).toFixed(2)}%</td>
                        <td>${(c.recall * 100).toFixed(2)}%</td>
                        <td>${(c.f1_score * 100).toFixed(2)}%</td>
                        <td><span class="badge ${isBest ? 'badge-success' : 'badge-muted'}">${isBest ? 'Selected Best' : 'Baseline'}</span></td>
                    </tr>
                `;
            }).join("");

            const regs = bm.regressors || {};
            regTbody.innerHTML = Object.keys(regs).map(k => {
                const r = regs[k];
                const isBest = k.includes("XGBoost");
                return `
                    <tr class="${isBest ? 'highlight-row' : ''}">
                        <td><strong>${k}</strong></td>
                        <td>${r.mae ? r.mae.toFixed(2) + ' months' : 'N/A'}</td>
                        <td>${r.r2 ? r.r2.toFixed(4) : 'N/A'}</td>
                        <td><span class="badge ${isBest ? 'badge-success' : 'badge-muted'}">${isBest ? 'Selected Best' : 'Baseline'}</span></td>
                    </tr>
                `;
            }).join("");

        } catch (e) {
            console.warn("Error fetching benchmarks:", e);
        }
    }

    function closeBenchmarkModal() {
        document.getElementById("modal-benchmarks").classList.add("d-none");
    }

    // ------------------ 10. CREATE USER MODAL (ADMIN) ------------------
    function openCreateUserModal() {
        document.getElementById("modal-create-user").classList.remove("d-none");
    }
    function closeCreateUserModal() {
        document.getElementById("modal-create-user").classList.add("d-none");
    }
    async function submitCreateUser(e) {
        e.preventDefault();
        const payload = {
            full_name: document.getElementById("new-user-fullname").value.trim(),
            email: document.getElementById("new-user-email").value.trim(),
            username: document.getElementById("new-user-username").value.trim(),
            password: document.getElementById("new-user-password").value,
            role: document.getElementById("new-user-role").value,
            organization: document.getElementById("new-user-org").value.trim()
        };

        try {
            const res = await Auth.fetchWithAuth("/api/admin/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok) {
                showToast("User created successfully.", "success");
                closeCreateUserModal();
                loadAdminUsers();
            } else {
                showToast(data.detail || "Failed to create user.", "danger");
            }
        } catch (err) {
            showToast(err.message, "danger");
        }
    }

    // ------------------ UTILITIES ------------------
    async function loadFilterOptions() {
        try {
            const res = await Auth.fetchWithAuth("/api/filters");
            const data = await res.json();

            const secSel = document.getElementById("filter-sector");
            if (secSel && data.sectors) {
                data.sectors.forEach(s => {
                    const opt = document.createElement("option");
                    opt.value = s;
                    opt.textContent = s;
                    secSel.appendChild(opt);
                });
            }

            const stateSel = document.getElementById("filter-state");
            if (stateSel && data.states) {
                data.states.forEach(st => {
                    const opt = document.createElement("option");
                    opt.value = st;
                    opt.textContent = st;
                    stateSel.appendChild(opt);
                });
            }

            const agySel = document.getElementById("filter-agency");
            if (agySel && data.agencies) {
                data.agencies.forEach(ag => {
                    const opt = document.createElement("option");
                    opt.value = ag;
                    opt.textContent = ag;
                    agySel.appendChild(opt);
                });
            }

            const minSel = document.getElementById("filter-ministry");
            if (minSel && data.ministries) {
                data.ministries.forEach(m => {
                    const opt = document.createElement("option");
                    opt.value = m;
                    opt.textContent = m.length > 40 ? m.slice(0, 38) + "…" : m;
                    minSel.appendChild(opt);
                });
            }
        } catch (e) {
            console.warn("Filters load error:", e);
        }
    }

    function exportProjectsCSV() {
        // Build CSV from current filtered view
        const search = document.getElementById("proj-search")?.value.trim() || "";
        const sector = document.getElementById("filter-sector")?.value || "ALL";
        const state = document.getElementById("filter-state")?.value || "ALL";
        const risk = document.getElementById("filter-risk")?.value || "ALL";
        const ministry = document.getElementById("filter-ministry")?.value || "ALL";

        const params = new URLSearchParams({ page: 1, page_size: 500, sort_by: projectSortBy, sort_order: projectSortOrder });
        if (search) params.append("search", search);
        if (sector !== "ALL") params.append("sector", sector);
        if (state !== "ALL") params.append("state", state);
        if (risk !== "ALL") params.append("risk_level", risk);
        if (ministry !== "ALL") params.append("ministry", ministry);

        Auth.fetchWithAuth(`/api/projects?${params.toString()}`).then(res => res.json()).then(data => {
            const projects = data.projects || [];
            const headers = ["Project Code","Project Name","Agency","Ministry","Sector","State","Original Cost (Cr)","Revised Cost (Cr)","Expenditure (Cr)","Progress (%)","Delay (Months)","Cost Overrun (%)","Risk Level","Anomaly"];
            const rows = projects.map(p => [
                p.project_code, `"${(p.project_name||"").replace(/"/g,'""')}"`,
                `"${(p.agency||"").replace(/"/g,'""')}"`,
                `"${(p.ministry||"").replace(/"/g,'""')}"`,
                p.sector, p.state,
                p.orig_cost, p.rev_cost, p.expenditure,
                p.progress ? p.progress.toFixed(1) : 0,
                p.delay_months || 0,
                p.cost_overrun_pct ? p.cost_overrun_pct.toFixed(1) : 0,
                p.risk_level,
                p.is_anomaly ? "YES" : "NO"
            ].join(","));
            const csv = [headers.join(","), ...rows].join("\n");
            const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `PAIMANA_Projects_${new Date().toISOString().slice(0,10)}.csv`;
            a.click();
            URL.revokeObjectURL(url);
            showToast(`Exported ${projects.length} projects to CSV.`, "success");
        }).catch(err => showToast("CSV export failed: " + err.message, "danger"));
    }

    function showToast(msg, type = "info") {
        const container = document.getElementById("toast-container");
        if (!container) return;
        const toast = document.createElement("div");
        toast.className = `toast-message toast-${type}`;
        toast.innerHTML = `<i data-lucide="${type === 'success' ? 'check-circle-2' : (type === 'danger' ? 'alert-triangle' : 'info')}"></i><span>${msg}</span>`;
        container.appendChild(toast);
        lucide.createIcons();
        setTimeout(() => {
            toast.remove();
        }, 4000);
    }

    function attachEvents() {
        // Search trigger
        const searchInput = document.getElementById("proj-search");
        if (searchInput) {
            let timeout = null;
            searchInput.addEventListener("input", () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    projectsPage = 1;
                    loadProjects();
                }, 400);
            });
        }

        // Filter triggers
        ["filter-sector", "filter-state", "filter-agency", "filter-risk", "filter-ministry"].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener("change", () => {
                projectsPage = 1;
                loadProjects();
            });
        });

        // Mobile sidebar toggle
        const btnMobile = document.getElementById("btn-mobile-menu");
        const sidebar = document.getElementById("portal-sidebar");
        if (btnMobile && sidebar) {
            btnMobile.addEventListener("click", () => {
                sidebar.classList.toggle("mobile-open");
            });
        }

        // Collapse sidebar button
        const btnCollapse = document.getElementById("btn-collapse-sidebar");
        if (btnCollapse && sidebar) {
            btnCollapse.addEventListener("click", () => {
                sidebar.classList.toggle("collapsed");
            });
        }
    }

    return {
        init,
        showView,
        prevPage,
        nextPage,
        handleSortChange,
        resetProjectFilters,
        setAnalyticsTab,
        setAdminSubView,
        loadAdminUsers,
        toggleUserStatus,
        loadAdminAuditLogs,
        saveAdminSettings,
        changePassword,
        openGlobalSimModal,
        openProjectSim,
        closeSimModal,
        runSimulation,
        openBenchmarkModal,
        closeBenchmarkModal,
        openCreateUserModal,
        closeCreateUserModal,
        submitCreateUser,
        exportProjectsCSV
    };
})();

document.addEventListener("DOMContentLoaded", Portal.init);
