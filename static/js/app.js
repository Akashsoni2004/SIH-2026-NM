/**
 * AI-POWERED INTEGRATED PROJECT MONITORING & RISK PREDICTION PLATFORM
 * Frontend Controller & Interactive Engine
 */

let state = {
    currentPage: 1,
    pageSize: 15,
    totalPages: 1,
    sortBy: "orig_cost",
    sortOrder: "desc",
    search: "",
    ministry: "ALL",
    sector: "ALL",
    stateFilter: "ALL",
    riskLevel: "ALL",
    isAnomaly: null,
    currentProject: null,
    charts: {
        sectorBar: null,
        riskDoughnut: null,
        drawerTrajectory: null
    }
};

document.addEventListener("DOMContentLoaded", () => {
    // Initialize Lucide icons
    if (window.lucide) {
        lucide.createIcons();
    }

    initDashboard();
    setupEventListeners();
});

async function initDashboard() {
    await Promise.all([
        loadDashboardStats(),
        loadFilterOptions(),
        loadAnomaliesTicker(),
        loadSectorAnalytics(),
        loadProjects()
    ]);
}

function setupEventListeners() {
    // Search input debounced
    let searchTimeout = null;
    const searchInput = document.getElementById("filter-search");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                state.search = e.target.value.trim();
                state.currentPage = 1;
                loadProjects();
            }, 300);
        });
    }

    // Filter changes
    document.getElementById("filter-ministry")?.addEventListener("change", (e) => {
        state.ministry = e.target.value;
        state.currentPage = 1;
        loadProjects();
    });

    document.getElementById("filter-sector")?.addEventListener("change", (e) => {
        state.sector = e.target.value;
        state.currentPage = 1;
        loadProjects();
    });

    document.getElementById("filter-state")?.addEventListener("change", (e) => {
        state.stateFilter = e.target.value;
        state.currentPage = 1;
        loadProjects();
    });

    document.getElementById("filter-risk")?.addEventListener("change", (e) => {
        state.riskLevel = e.target.value;
        state.currentPage = 1;
        loadProjects();
    });

    document.getElementById("filter-anomaly")?.addEventListener("change", (e) => {
        state.isAnomaly = e.target.value === "ALL" ? null : parseInt(e.target.value);
        state.currentPage = 1;
        loadProjects();
    });

    document.getElementById("btn-reset-filters")?.addEventListener("click", () => {
        state.search = "";
        state.ministry = "ALL";
        state.sector = "ALL";
        state.stateFilter = "ALL";
        state.riskLevel = "ALL";
        state.isAnomaly = null;
        
        if (searchInput) searchInput.value = "";
        document.getElementById("filter-ministry").value = "ALL";
        document.getElementById("filter-sector").value = "ALL";
        document.getElementById("filter-state").value = "ALL";
        document.getElementById("filter-risk").value = "ALL";
        document.getElementById("filter-anomaly").value = "ALL";
        
        state.currentPage = 1;
        loadProjects();
    });

    // Sortable headers
    document.querySelectorAll(".project-table th.sortable").forEach(th => {
        th.addEventListener("click", () => {
            const field = th.dataset.sort;
            if (state.sortBy === field) {
                state.sortOrder = state.sortOrder === "desc" ? "asc" : "desc";
            } else {
                state.sortBy = field;
                state.sortOrder = "desc";
            }
            loadProjects();
        });
    });

    // Pagination buttons
    document.getElementById("btn-prev-page")?.addEventListener("click", () => {
        if (state.currentPage > 1) {
            state.currentPage--;
            loadProjects();
        }
    });

    document.getElementById("btn-next-page")?.addEventListener("click", () => {
        if (state.currentPage < state.totalPages) {
            state.currentPage++;
            loadProjects();
        }
    });

    // Drawer close buttons
    document.getElementById("btn-close-drawer")?.addEventListener("click", closeProjectDrawer);
    document.getElementById("drawer-overlay")?.addEventListener("click", closeProjectDrawer);

    // What-If Simulation Modal
    document.getElementById("btn-open-sim")?.addEventListener("click", openSimModal);
    document.getElementById("btn-close-sim")?.addEventListener("click", closeSimModal);
    document.getElementById("sim-modal-overlay")?.addEventListener("click", (e) => {
        if (e.target.id === "sim-modal-overlay") closeSimModal();
    });

    // ML Benchmark Modal
    document.getElementById("btn-open-benchmark")?.addEventListener("click", openBenchmarkModal);
    document.getElementById("btn-close-benchmark")?.addEventListener("click", closeBenchmarkModal);
    document.getElementById("benchmark-modal-overlay")?.addEventListener("click", (e) => {
        if (e.target.id === "benchmark-modal-overlay") closeBenchmarkModal();
    });

    // Quick filter anomalies from ticker or doughnut legend
    document.getElementById("btn-view-anomalies")?.addEventListener("click", () => {
        const anomSelect = document.getElementById("filter-anomaly");
        if (anomSelect) anomSelect.value = "1";
        state.isAnomaly = 1;
        state.currentPage = 1;
        loadProjects();
        document.getElementById("projects-section")?.scrollIntoView({ behavior: "smooth" });
    });

    document.getElementById("legend-anom-btn")?.addEventListener("click", () => {
        const anomSelect = document.getElementById("filter-anomaly");
        if (anomSelect) anomSelect.value = "1";
        state.isAnomaly = 1;
        state.currentPage = 1;
        loadProjects();
        document.getElementById("projects-section")?.scrollIntoView({ behavior: "smooth" });
    });

    // Simulation Slider Interactions
    setupSimSliders();
}

// ----------------- DATA LOADING FUNCTIONS -----------------

async function loadDashboardStats() {
    try {
        const res = await fetch("/api/dashboard/stats");
        const data = await res.json();

        document.getElementById("stat-total-projects").textContent = formatNumber(data.total_projects);
        document.getElementById("stat-rev-cost").textContent = `₹${(data.total_revised_cost_cr / 100000).toFixed(2)}L Cr`;
        document.getElementById("stat-cost-growth").textContent = `+₹${(data.total_cost_growth_cr / 100000).toFixed(2)}L Cr Escalation`;
        
        document.getElementById("stat-high-risk").textContent = formatNumber(data.high_risk_count);
        const highPct = ((data.high_risk_count / data.total_projects) * 100).toFixed(1);
        document.getElementById("stat-high-risk-pct").textContent = `${highPct}%`;

        document.getElementById("stat-avg-delay").textContent = data.average_delay_months;
        document.getElementById("stat-delayed-count").textContent = `${data.delayed_projects_count} Delayed`;

        document.getElementById("stat-avg-progress").textContent = `${data.average_physical_progress_pct}%`;

        // Update Doughnut legend & center
        document.getElementById("donut-total").textContent = formatNumber(data.total_projects);
        document.getElementById("legend-high").textContent = `${formatNumber(data.high_risk_count)} (${highPct}%)`;
        document.getElementById("legend-med").textContent = `${formatNumber(data.medium_risk_count)} (${((data.medium_risk_count / data.total_projects) * 100).toFixed(0)}%)`;
        document.getElementById("legend-low").textContent = `${formatNumber(data.low_risk_count)} (${((data.low_risk_count / data.total_projects) * 100).toFixed(0)}%)`;
        document.getElementById("legend-anom").textContent = `${data.anomaly_projects_count} projects`;

        renderRiskDoughnut(data.high_risk_count, data.medium_risk_count, data.low_risk_count);
    } catch (err) {
        console.error("Failed to load dashboard stats:", err);
    }
}

async function loadFilterOptions() {
    try {
        const res = await fetch("/api/filters");
        const data = await res.json();

        populateSelect("filter-ministry", data.ministries, "All Ministries");
        populateSelect("filter-sector", data.sectors, "All Sectors");
        populateSelect("filter-state", data.states, "All States");
    } catch (err) {
        console.error("Failed to load filter options:", err);
    }
}

function populateSelect(elemId, items, defaultLabel) {
    const select = document.getElementById(elemId);
    if (!select) return;

    select.innerHTML = `<option value="ALL">${defaultLabel} (${items.length})</option>`;
    items.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item;
        opt.textContent = item;
        select.appendChild(opt);
    });
}

async function loadAnomaliesTicker() {
    try {
        const res = await fetch("/api/anomalies?limit=10");
        const anomalies = await res.json();

        const slider = document.getElementById("ticker-slider");
        if (!slider) return;

        if (!anomalies || anomalies.length === 0) {
            slider.innerHTML = `<span class="ticker-item">No critical execution anomalies detected.</span>`;
            return;
        }

        slider.innerHTML = "";
        let currentIndex = 0;

        function updateTicker() {
            const anom = anomalies[currentIndex];
            slider.innerHTML = `
                <span class="ticker-item" style="cursor: pointer;" onclick="openProjectDetail('${anom.project_code}')">
                    <strong>⚠️ [Code: ${anom.project_code}] ${escapeHtml(anom.project_name.substring(0, 60))}...</strong>: 
                    ${escapeHtml(anom.anomaly_reason)} (Click to Inspect)
                </span>
            `;
            currentIndex = (currentIndex + 1) % anomalies.length;
        }

        updateTicker();
        setInterval(updateTicker, 6000);
    } catch (err) {
        console.error("Failed to load anomalies ticker:", err);
    }
}

async function loadSectorAnalytics() {
    try {
        const res = await fetch("/api/analytics/sectors");
        const sectors = await res.json();

        renderSectorBarChart(sectors.slice(0, 8));
    } catch (err) {
        console.error("Failed to load sector analytics:", err);
    }
}

async function loadProjects() {
    const tbody = document.getElementById("projectTableBody");
    if (!tbody) return;

    tbody.innerHTML = `
        <tr>
            <td colspan="9" class="table-loading">
                <div class="spinner"></div>
                <span>Filtering 1,737 infrastructure projects...</span>
            </td>
        </tr>
    `;

    try {
        const params = new URLSearchParams({
            page: state.currentPage,
            page_size: state.pageSize,
            sort_by: state.sortBy,
            sort_order: state.sortOrder
        });

        if (state.search) params.append("search", state.search);
        if (state.ministry !== "ALL") params.append("ministry", state.ministry);
        if (state.sector !== "ALL") params.append("sector", state.sector);
        if (state.stateFilter !== "ALL") params.append("state", state.stateFilter);
        if (state.riskLevel !== "ALL") params.append("risk_level", state.riskLevel);
        if (state.isAnomaly !== null) params.append("is_anomaly", state.isAnomaly);

        const res = await fetch(`/api/projects?${params.toString()}`);
        const data = await res.json();

        state.totalPages = data.total_pages || 1;
        document.getElementById("table-total-badge").textContent = `${formatNumber(data.total)} Projects`;

        renderProjectTable(data.projects);
        updatePagination(data.total, data.page, data.page_size, data.total_pages);
    } catch (err) {
        console.error("Failed to load projects:", err);
        tbody.innerHTML = `<tr><td colspan="9" class="text-center p-4 text-red">Failed to load projects. Check API server.</td></tr>`;
    }
}

function renderProjectTable(projects) {
    const tbody = document.getElementById("projectTableBody");
    if (!tbody) return;

    if (!projects || projects.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="table-loading">
                    <span>No infrastructure projects match your filter criteria.</span>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = projects.map(p => {
        const riskClass = p.risk_level === "HIGH" ? "badge-high" : (p.risk_level === "MEDIUM" ? "badge-med" : "badge-low");
        const delayDisplay = p.delay_months > 0 ? `${p.delay_months}m Delay` : (p.delay_months < 0 ? `${Math.abs(p.delay_months)}m Early` : "On Time");
        const delayColor = p.delay_months > 12 ? "text-red" : (p.delay_months > 0 ? "text-amber" : "text-emerald");
        
        const costEscalation = p.cost_growth > 0 ? `<span class="cost-growth-badge">+₹${formatNumber(p.cost_growth)} Cr (${p.cost_overrun_pct.toFixed(1)}%)</span>` : "";

        return `
            <tr onclick="openProjectDetail('${p.project_code}')">
                <td class="col-code">${p.project_code}</td>
                <td class="col-name">
                    <span class="p-title">${escapeHtml(p.project_name)}</span>
                    <span class="p-agency">${escapeHtml(p.agency || "Executing Agency")}</span>
                </td>
                <td>
                    <span class="p-sector-badge">${escapeHtml(p.sector)}</span>
                    <span class="p-state">${escapeHtml(p.state)}</span>
                </td>
                <td class="col-cost">₹${formatNumber(p.orig_cost)} Cr</td>
                <td class="col-cost">
                    ₹${formatNumber(p.rev_cost)} Cr
                    ${costEscalation}
                </td>
                <td class="col-prog">
                    <div><strong>${p.progress.toFixed(1)}%</strong></div>
                    <div class="table-progress-bar-bg">
                        <div class="table-progress-bar-fill" style="width: ${Math.min(100, Math.max(0, p.progress))}%"></div>
                    </div>
                </td>
                <td class="col-delay ${delayColor}"><strong>${delayDisplay}</strong></td>
                <td>
                    <span class="badge-risk ${riskClass}">${p.risk_level} RISK</span>
                    ${p.is_anomaly ? '<span class="legend-dot dot-purple" title="AI Anomaly Flagged" style="display:inline-block; margin-left:4px;"></span>' : ''}
                </td>
                <td>
                    <button class="table-inspect-btn">
                        Inspect
                    </button>
                </td>
            </tr>
        `;
    }).join("");

    if (window.lucide) {
        lucide.createIcons();
    }
}

function updatePagination(total, page, pageSize, totalPages) {
    const start = Math.min((page - 1) * pageSize + 1, total);
    const end = Math.min(page * pageSize, total);
    document.getElementById("pagination-info").textContent = `Showing ${start} to ${end} of ${formatNumber(total)} projects`;

    const prevBtn = document.getElementById("btn-prev-page");
    const nextBtn = document.getElementById("btn-next-page");

    if (prevBtn) prevBtn.disabled = page <= 1;
    if (nextBtn) nextBtn.disabled = page >= totalPages;

    const pageNumbers = document.getElementById("page-numbers");
    if (!pageNumbers) return;

    pageNumbers.innerHTML = "";
    
    // Compute small window of page numbers
    let startPage = Math.max(1, page - 2);
    let endPage = Math.min(totalPages, page + 2);

    for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement("button");
        btn.className = `page-num ${i === page ? 'active' : ''}`;
        btn.textContent = i;
        btn.onclick = () => {
            state.currentPage = i;
            loadProjects();
        };
        pageNumbers.appendChild(btn);
    }
}

// ----------------- PROJECT DEEP DIVE DRAWER -----------------

async function openProjectDetail(projectCode) {
    try {
        const res = await fetch(`/api/projects/${projectCode}`);
        if (!res.ok) throw new Error("Project not found");
        const p = await res.json();
        state.currentProject = p;

        // Populate Drawer Content
        document.getElementById("drawer-code").textContent = `CODE: ${p.project_code}`;
        document.getElementById("drawer-name").textContent = p.project_name;
        document.getElementById("drawer-agency").textContent = `${p.agency} • ${p.ministry}`;

        const riskBadge = document.getElementById("drawer-risk-badge");
        riskBadge.textContent = `${p.risk_level} RISK`;
        riskBadge.className = `drawer-risk-badge ${p.risk_level === 'HIGH' ? 'badge-high' : (p.risk_level === 'MEDIUM' ? 'badge-med' : 'badge-low')}`;

        const anomBadge = document.getElementById("drawer-anomaly-badge");
        anomBadge.style.display = p.is_anomaly ? "inline-block" : "none";

        // AI Prediction Highlights
        const pred = p.ai_prediction || {};
        document.getElementById("drawer-ai-score").textContent = `${pred.risk_score || 50}%`;
        document.getElementById("drawer-ai-score-bar").style.width = `${pred.risk_score || 50}%`;
        
        let levelDesc = "Normal Milestone Progress";
        if (p.risk_level === "HIGH") levelDesc = "Critical Intervention Recommended";
        else if (p.risk_level === "MEDIUM") levelDesc = "Moderate Variance — Review Milestones";
        document.getElementById("drawer-ai-level-desc").textContent = levelDesc;

        document.getElementById("drawer-pred-delay").textContent = pred.predicted_delay_days || 0;
        document.getElementById("drawer-target-doc-sub").textContent = `Target: ${p.target_doc || 'NA'} • Revised: ${p.revised_doc || 'NA'}`;

        document.getElementById("drawer-pred-overrun").textContent = `+${(pred.predicted_cost_overrun_pct || 0).toFixed(1)}%`;
        document.getElementById("drawer-final-cost-sub").textContent = `Exp. Final: ₹${formatNumber(pred.predicted_final_cost || p.rev_cost)} Cr`;

        // 4-Month Velocity Metrics
        document.getElementById("drawer-prog-vel").textContent = `${p.progress_velocity >= 0 ? '+' : ''}${p.progress_velocity.toFixed(1)}%/mo`;
        document.getElementById("drawer-exp-vel").textContent = `₹${p.expenditure_velocity.toFixed(1)} Cr/mo`;
        document.getElementById("drawer-delay-slip").textContent = `${p.delay_slippage > 0 ? '+' : ''}${p.delay_slippage} months`;

        // Project Parameters Details Grid
        document.getElementById("d-ministry").textContent = p.ministry;
        document.getElementById("d-sector").textContent = p.sector;
        document.getElementById("d-state").textContent = p.state;
        document.getElementById("d-orig-cost").textContent = `₹${formatNumber(p.orig_cost)} Cr`;
        document.getElementById("d-rev-cost").textContent = `₹${formatNumber(p.rev_cost)} Cr`;
        document.getElementById("d-expenditure").textContent = `₹${formatNumber(p.expenditure)} Cr`;
        document.getElementById("d-fin-prog").textContent = `${p.financial_progress_pct.toFixed(1)}%`;
        document.getElementById("d-progress").textContent = `${p.progress.toFixed(1)}%`;
        document.getElementById("d-app-date").textContent = p.app_date || "NA";
        document.getElementById("d-target-doc").textContent = p.target_doc || "NA";
        document.getElementById("d-rev-doc").textContent = p.revised_doc || "NA";
        document.getElementById("d-gap").textContent = `${p.progress_gap >= 0 ? '+' : ''}${p.progress_gap.toFixed(1)}%`;

        // Explainable AI Risk Factors
        const factorsList = document.getElementById("drawer-risk-factors");
        factorsList.innerHTML = (pred.risk_factors || []).map(rf => `
            <div class="factor-item">
                <div class="factor-top-row">
                    <span class="factor-name">${escapeHtml(rf.factor)}</span>
                    <span class="factor-pct">${rf.contribution_pct}%</span>
                </div>
                <div class="factor-bar-bg">
                    <div class="factor-bar-fill" style="width: ${Math.min(100, rf.contribution_pct)}%"></div>
                </div>
            </div>
        `).join("");

        // Recommendations List
        const recomsList = document.getElementById("drawer-recommendations");
        recomsList.innerHTML = (pred.recommendations || []).map(r => {
            const sevClass = r.severity === 'CRITICAL' ? 'recom-critical' : (r.severity === 'HIGH' ? 'recom-high' : (r.severity === 'MEDIUM' ? 'recom-medium' : 'recom-low'));
            const badgeClass = r.severity === 'CRITICAL' ? 'badge-crit' : (r.severity === 'HIGH' ? 'badge-h' : (r.severity === 'MEDIUM' ? 'badge-m' : 'badge-l'));
            return `
                <div class="recom-item ${sevClass}">
                    <div class="recom-icon-col">
                        <i data-lucide="${r.severity === 'CRITICAL' ? 'alert-octagon' : (r.severity === 'HIGH' ? 'alert-triangle' : 'info')}"></i>
                    </div>
                    <div class="recom-content">
                        <div class="recom-title-row">
                            <span class="recom-title">${escapeHtml(r.title)}</span>
                            <span class="recom-badge ${badgeClass}">${r.severity}</span>
                        </div>
                        <p class="recom-desc">${escapeHtml(r.action)}</p>
                    </div>
                </div>
            `;
        }).join("");

        // Render Longitudinal Trajectory Chart
        renderDrawerTrajectoryChart(p.history || []);

        // Show Drawer
        document.getElementById("drawer-overlay")?.classList.add("active");
        document.getElementById("project-drawer")?.classList.add("active");

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error("Error opening project details:", err);
    }
}

function closeProjectDrawer() {
    document.getElementById("drawer-overlay")?.classList.remove("active");
    document.getElementById("project-drawer")?.classList.remove("active");
}

// ----------------- CHARTS RENDERING -----------------

function renderSectorBarChart(sectorData) {
    const ctx = document.getElementById("sectorBarChart")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.sectorBar) {
        state.charts.sectorBar.destroy();
    }

    const labels = sectorData.map(s => s.sector.length > 20 ? s.sector.substring(0, 18) + '...' : s.sector);
    const costs = sectorData.map(s => Math.round(s.total_rev_cost));
    const delays = sectorData.map(s => s.avg_delay);

    state.charts.sectorBar = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Revised Cost (₹ Cr)',
                    data: costs,
                    backgroundColor: 'rgba(99, 102, 241, 0.75)',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    borderRadius: 6,
                    yAxisID: 'y'
                },
                {
                    label: 'Avg Delay (Months)',
                    data: delays,
                    type: 'line',
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.2)',
                    borderWidth: 2,
                    pointBackgroundColor: '#f59e0b',
                    pointRadius: 4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } }
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 10
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#64748b', font: { family: 'Inter', size: 11 } }
                },
                y: {
                    type: 'linear',
                    position: 'left',
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#64748b',
                        callback: val => `₹${(val / 1000).toFixed(0)}k Cr`
                    }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: '#f59e0b',
                        callback: val => `${val}m`
                    }
                }
            }
        }
    });
}

function renderRiskDoughnut(high, med, low) {
    const ctx = document.getElementById("riskDoughnutChart")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.riskDoughnut) {
        state.charts.riskDoughnut.destroy();
    }

    state.charts.riskDoughnut = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['High Risk', 'Medium Risk', 'Low Risk'],
            datasets: [{
                data: [high, med, low],
                backgroundColor: [
                    '#ef4444',
                    '#f59e0b',
                    '#10b981'
                ],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '76%',
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#ffffff',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 8
                }
            }
        }
    });
}

function renderDrawerTrajectoryChart(history) {
    const ctx = document.getElementById("drawerTrajectoryChart")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.drawerTrajectory) {
        state.charts.drawerTrajectory.destroy();
    }

    const labels = history.map(h => h.month);
    const progresses = history.map(h => h.progress);
    const expenditures = history.map(h => h.expenditure);

    state.charts.drawerTrajectory = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Physical Progress (%)',
                    data: progresses,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.3,
                    yAxisID: 'y'
                },
                {
                    label: 'Cumulative Expenditure (₹ Cr)',
                    data: expenditures,
                    borderColor: '#6366f1',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.3,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { color: '#64748b' }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: {
                        color: '#10b981',
                        callback: val => `${val}%`
                    }
                },
                y1: {
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: '#6366f1',
                        callback: val => `₹${val} Cr`
                    }
                }
            }
        }
    });
}

// ----------------- WHAT-IF SIMULATION LAB -----------------

function setupSimSliders() {
    const origInput = document.getElementById("sim-orig-cost");
    const revInput = document.getElementById("sim-rev-cost");
    const expInput = document.getElementById("sim-expenditure");
    const progInput = document.getElementById("sim-progress");

    origInput?.addEventListener("input", e => {
        document.getElementById("val-sim-orig").textContent = `₹${formatNumber(e.target.value)} Cr`;
    });

    revInput?.addEventListener("input", e => {
        document.getElementById("val-sim-rev").textContent = `₹${formatNumber(e.target.value)} Cr`;
    });

    expInput?.addEventListener("input", e => {
        document.getElementById("val-sim-exp").textContent = `₹${formatNumber(e.target.value)} Cr`;
    });

    progInput?.addEventListener("input", e => {
        document.getElementById("val-sim-prog").textContent = `${e.target.value}%`;
    });

    document.getElementById("btn-run-simulation")?.addEventListener("click", runSimulation);
}

function openSimModal() {
    document.getElementById("sim-modal-overlay")?.classList.add("active");
    if (window.lucide) lucide.createIcons();
}

function closeSimModal() {
    document.getElementById("sim-modal-overlay")?.classList.remove("active");
}

async function runSimulation() {
    const orig = parseFloat(document.getElementById("sim-orig-cost")?.value || 1000);
    const rev = parseFloat(document.getElementById("sim-rev-cost")?.value || 1200);
    const exp = parseFloat(document.getElementById("sim-expenditure")?.value || 750);
    const prog = parseFloat(document.getElementById("sim-progress")?.value || 45);
    const pv = parseFloat(document.getElementById("sim-prog-vel")?.value || 0.8);
    const slip = parseFloat(document.getElementById("sim-slip")?.value || 2);

    try {
        const res = await fetch("/api/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                orig_cost: orig,
                rev_cost: rev,
                expenditure: exp,
                progress: prog,
                progress_velocity: pv,
                delay_slippage: slip,
                time_elapsed_months: 24,
                planned_duration_months: 36
            })
        });

        const pred = await res.json();

        const riskElem = document.getElementById("sim-res-risk");
        riskElem.textContent = `${pred.risk_level} RISK`;
        riskElem.className = `badge-risk ${pred.risk_level === 'HIGH' ? 'badge-high' : (pred.risk_level === 'MEDIUM' ? 'badge-med' : 'badge-low')}`;

        document.getElementById("sim-res-score").textContent = `Risk Score: ${pred.risk_score}%`;
        document.getElementById("sim-res-delay").textContent = `${pred.predicted_delay_days} Days`;
        document.getElementById("sim-res-overrun").textContent = `+${pred.predicted_cost_overrun_pct.toFixed(1)}%`;
        
        const anomElem = document.getElementById("sim-res-anom");
        anomElem.textContent = pred.is_anomaly ? "Flagged Anomaly" : "Normal";
        anomElem.className = `smc-val ${pred.is_anomaly ? 'text-red' : 'text-emerald'}`;

        const firstRecom = (pred.recommendations && pred.recommendations[0]) ? pred.recommendations[0].action : "Project progressing normally.";
        document.getElementById("sim-res-action").textContent = firstRecom;

    } catch (err) {
        console.error("Failed to run simulation:", err);
    }
}

// ----------------- ML BENCHMARK MODAL -----------------

async function openBenchmarkModal() {
    document.getElementById("benchmark-modal-overlay")?.classList.add("active");
    try {
        const res = await fetch("/api/model/benchmarks");
        const data = await res.json();

        // Classification benchmarks
        const clsBody = document.getElementById("bm-classification-tbody");
        if (clsBody && data.classification) {
            clsBody.innerHTML = data.classification.map(m => `
                <tr>
                    <td><strong>${escapeHtml(m.model)}</strong></td>
                    <td>${(m.accuracy * 100).toFixed(2)}%</td>
                    <td>${(m.precision * 100).toFixed(2)}%</td>
                    <td>${(m.recall * 100).toFixed(2)}%</td>
                    <td>${(m.f1 * 100).toFixed(2)}%</td>
                    <td>
                        <span class="${m.model.includes('Selected') ? 'bm-badge-selected' : 'bm-badge-base'}">
                            ${m.model.includes('Selected') ? 'Selected' : 'Baseline'}
                        </span>
                    </td>
                </tr>
            `).join("");
        }

        // Delay Regression benchmarks
        const regBody = document.getElementById("bm-delay-tbody");
        if (regBody && data.delay_regression) {
            regBody.innerHTML = data.delay_regression.map(m => `
                <tr>
                    <td><strong>${escapeHtml(m.model)}</strong></td>
                    <td>${m.mae.toFixed(2)} months</td>
                    <td>${m.r2.toFixed(4)}</td>
                    <td>
                        <span class="${m.model.includes('Selected') ? 'bm-badge-selected' : 'bm-badge-base'}">
                            ${m.model.includes('Selected') ? 'Selected' : 'Baseline'}
                        </span>
                    </td>
                </tr>
            `).join("");
        }

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error("Failed to load benchmarks:", err);
    }
}

function closeBenchmarkModal() {
    document.getElementById("benchmark-modal-overlay")?.classList.remove("active");
}

// ----------------- UTILITY HELPERS -----------------

function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return "0";
    return Number(num).toLocaleString('en-IN');
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
