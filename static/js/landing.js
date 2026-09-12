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
    const menuLinks = document.querySelectorAll(".public-menu a");
    menuLinks.forEach(anchor => {
        anchor.addEventListener("click", function(e) {
            const href = this.getAttribute("href");
            if (href.startsWith("#")) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: "smooth", block: "start" });
                }
                menuLinks.forEach(a => a.classList.remove("active"));
                this.classList.add("active");
            }
        });
    });

    // 3. Scroll Spy for Navigation Active State
    const sections = document.querySelectorAll("section[id]");
    if ("IntersectionObserver" in window && sections.length > 0) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.getAttribute("id");
                    menuLinks.forEach(link => {
                        if (link.getAttribute("href") === `#${id}`) {
                            link.classList.add("active");
                        } else {
                            link.classList.remove("active");
                        }
                    });
                }
            });
        }, {
            threshold: 0.35,
            rootMargin: "-80px 0px -50% 0px"
        });

        sections.forEach(sec => observer.observe(sec));
    }

    // 4. Initialize Lucide Icons
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
});
