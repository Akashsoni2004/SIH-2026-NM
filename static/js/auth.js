/**
 * PAIMANA AI - Authentication & Role-Based Access Control Client Manager
 * SIH 2026 | Neural Minds
 */

const AuthManager = (function() {
    const TOKEN_KEY = "paimana_token";
    const USER_KEY = "paimana_user";

    function setSession(token, user) {
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        // Set cookie for HTTP requests
        document.cookie = `paimana_auth_token=${token}; path=/; max-age=${86400 * 2}; SameSite=Lax`;
    }

    function clearSession() {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        document.cookie = "paimana_auth_token=; path=/; max-age=0";
    }

    function getToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function getUser() {
        try {
            const raw = localStorage.getItem(USER_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    function isLoggedIn() {
        const token = getToken();
        const user = getUser();
        return !!(token && user);
    }

    function hasRole(roles) {
        const user = getUser();
        if (!user) return false;
        if (Array.isArray(roles)) {
            return roles.includes(user.role);
        }
        return user.role === roles;
    }

    async function login(username, password, portalType = "user") {
        try {
            const res = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password, portal_type: portalType })
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Authentication failed. Please check credentials.");
            }
            setSession(data.token, data.user);
            return data;
        } catch (err) {
            throw err;
        }
    }

    async function logout() {
        try {
            const token = getToken();
            if (token) {
                await fetch("/api/auth/logout", {
                    method: "POST",
                    headers: { "Authorization": `Bearer ${token}` }
                });
            }
        } catch (e) {
            console.warn("Logout notification error:", e);
        } finally {
            clearSession();
            window.location.href = "/login";
        }
    }

    async function fetchWithAuth(url, options = {}) {
        const token = getToken();
        const headers = options.headers || {};
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        options.headers = headers;

        const res = await fetch(url, options);

        if (res.status === 401) {
            clearSession();
            const isAdminPath = window.location.pathname.startsWith("/admin");
            window.location.href = isAdminPath ? "/admin/login?reason=session_expired" : "/login?reason=session_expired";
            throw new Error("Session expired. Please log in again.");
        }

        if (res.status === 403) {
            const data = await res.clone().json().catch(() => ({ detail: "Access Denied: You do not have permission to access this resource." }));
            throw new Error(data.detail || "Access Denied: 403 Forbidden");
        }

        return res;
    }

    function guardRoute() {
        const path = window.location.pathname;
        const publicPaths = ["/", "/login", "/admin/login"];
        
        if (publicPaths.includes(path)) {
            return;
        }

        if (!isLoggedIn()) {
            if (path.startsWith("/admin")) {
                window.location.href = "/admin/login?redirect=" + encodeURIComponent(path);
            } else {
                window.location.href = "/login?redirect=" + encodeURIComponent(path);
            }
            return;
        }

        const user = getUser();
        // Section 19: Strict check for admin route
        if (path.startsWith("/admin") && user.role !== "ADMIN") {
            window.location.href = "/dashboard?error=admin_access_denied";
        }
    }

    return {
        login,
        logout,
        getToken,
        getUser,
        isLoggedIn,
        hasRole,
        fetchWithAuth,
        clearSession,
        guardRoute
    };
})();

window.Auth = AuthManager;
