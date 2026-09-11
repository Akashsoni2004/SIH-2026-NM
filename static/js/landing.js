/**
 * PAIMANA AI - Landing Page Interactions & Dynamic Metrics Fetcher
 * SIH 2026 | Neural Minds
 */

document.addEventListener("DOMContentLoaded", async function() {
    // 1. Fetch live metrics from backend
    try {
        const res = await fetch("/api/dashboard/stats");
        if (res.ok) {
            const data = await res.json();
            
            // Format capital value
            const costCr = data.total_revised_cost_cr || 3654000;
            const costLakhCr = (costCr / 100000).toFixed(2);
            
            // Update hero values
            const heroProj = document.getElementById("hero-projects-count");
            if (heroProj) heroProj.textContent = Number(data.total_projects).toLocaleString();
            
            const heroCap = document.getElementById("hero-capital-val");
            if (heroCap) heroCap.textContent = `₹${costLakhCr}L Cr`;
            
            // Update impact section
            const statMonitored = document.getElementById("stat-monitored-proj");
            if (statMonitored) statMonitored.textContent = Number(data.total_projects).toLocaleString();
            
            const statHighRisk = document.getElementById("stat-high-risk-proj");
            if (statHighRisk) statHighRisk.textContent = Number(data.high_risk_count).toLocaleString();
            
            const statDelayed = document.getElementById("stat-delayed-proj");
            if (statDelayed) statDelayed.textContent = Number(data.delayed_projects_count).toLocaleString();
            
            const statAnom = document.getElementById("stat-anomalies-detected");
            if (statAnom) statAnom.textContent = Number(data.anomaly_projects_count).toLocaleString();
        }
    } catch (err) {
        console.warn("Could not fetch live dashboard metrics for landing page:", err);
    }

    // 2. Smooth Scroll for Navigation
    document.querySelectorAll(".public-menu a").forEach(anchor => {
        anchor.addEventListener("click", function(e) {
            const href = this.getAttribute("href");
            if (href.startsWith("#")) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: "smooth", block: "start" });
                }
                document.querySelectorAll(".public-menu a").forEach(a => a.classList.remove("active"));
                this.classList.add("active");
            }
        });
    });
});
