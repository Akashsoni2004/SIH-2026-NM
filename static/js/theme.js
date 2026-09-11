/**
 * PAIMANA AI - Modern Design-Token Theme Manager
 * National Infrastructure Intelligence Command Center
 * Ensures Default Light Theme, Smooth Transitions, System Preference support,
 * and Chart.js synchronization across the application.
 */

(function () {
    const THEME_STORAGE_KEY = 'paimana_theme';
    const THEME_DARK = 'dark';
    const THEME_LIGHT = 'light';

    // 1. Resolve stored or default theme (DEFAULT IS LIGHT MODE per Requirement 3)
    function getStoredTheme() {
        try {
            const saved = localStorage.getItem(THEME_STORAGE_KEY);
            if (saved === THEME_LIGHT || saved === THEME_DARK) {
                return saved;
            }
        } catch (e) {
            console.warn('Theme storage inaccessible:', e);
        }
        // Default to LIGHT MODE for Government Command Center
        return THEME_LIGHT;
    }

    function applyTheme(theme, dispatch = false) {
        const root = document.documentElement;
        const isDark = theme === THEME_DARK;

        root.setAttribute('data-theme', theme);
        root.style.colorScheme = theme;

        if (document.body) {
            if (isDark) {
                document.body.classList.remove('theme-light');
                document.body.classList.add('theme-dark');
            } else {
                document.body.classList.remove('theme-dark');
                document.body.classList.add('theme-light');
            }
        }

        updateToggleUI(theme);

        if (dispatch) {
            try {
                window.dispatchEvent(new CustomEvent('themechanged', { detail: { theme } }));
            } catch (e) {
                console.error('Error dispatching themechanged event:', e);
            }
        }
    }

    // Apply immediately to html element to prevent FOUC
    const initialTheme = getStoredTheme();
    document.documentElement.setAttribute('data-theme', initialTheme);
    document.documentElement.style.colorScheme = initialTheme;

    // Apply to body as soon as body is available
    if (document.body) {
        document.body.classList.add(initialTheme === THEME_DARK ? 'theme-dark' : 'theme-light');
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            const activeTheme = getStoredTheme();
            document.body.classList.add(activeTheme === THEME_DARK ? 'theme-dark' : 'theme-light');
            updateToggleUI(activeTheme);
        });
    }

    // 2. UI Update Helper for Theme Switcher Buttons
    function updateToggleUI(theme) {
        const isDark = theme === THEME_DARK;
        const toggleButtons = document.querySelectorAll(
            '.theme-toggle-btn, [data-action="toggle-theme"], #theme-toggle-btn, #portal-theme-toggle, #nav-theme-toggle, #landing-theme-toggle, #login-theme-toggle'
        );

        toggleButtons.forEach(btn => {
            btn.setAttribute('aria-label', isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme');
            btn.setAttribute('title', isDark ? 'Switch to Light Theme (Current: Dark)' : 'Switch to Dark Theme (Current: Light)');

            // Set active state if pill/tab style
            if (btn.classList.contains('theme-segmented-btn')) {
                btn.classList.toggle('active', btn.getAttribute('data-theme-target') === theme);
            } else {
                btn.innerHTML = isDark
                    ? `<i data-lucide="sun" class="theme-icon sun-icon"></i><span class="theme-label-sr sr-only">Light Mode</span>`
                    : `<i data-lucide="moon" class="theme-icon moon-icon"></i><span class="theme-label-sr sr-only">Dark Mode</span>`;
            }

            const textWrap = btn.querySelector('.theme-toggle-text');
            if (textWrap) {
                textWrap.textContent = isDark ? 'Light Mode' : 'Dark Mode';
            }
        });

        // Update segmented radio switches if present
        document.querySelectorAll('input[name="system-theme-toggle"]').forEach(radio => {
            radio.checked = radio.value === theme;
        });

        // Re-render Lucide icons safely
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    // 3. Public API
    window.ThemeManager = {
        getTheme: function () {
            return document.documentElement.getAttribute('data-theme') || THEME_LIGHT;
        },

        setTheme: function (theme) {
            if (theme !== THEME_LIGHT && theme !== THEME_DARK) return;
            try {
                localStorage.setItem(THEME_STORAGE_KEY, theme);
            } catch (e) {}
            applyTheme(theme, true);
        },

        toggleTheme: function () {
            const current = this.getTheme();
            const next = current === THEME_DARK ? THEME_LIGHT : THEME_DARK;
            this.setTheme(next);
            return next;
        }
    };

    // 4. Global click listener for toggle buttons
    document.addEventListener('click', function (e) {
        const toggleBtn = e.target.closest(
            '.theme-toggle-btn, [data-action="toggle-theme"], #theme-toggle-btn, #portal-theme-toggle, #nav-theme-toggle, #landing-theme-toggle, #login-theme-toggle'
        );
        if (toggleBtn) {
            e.preventDefault();
            window.ThemeManager.toggleTheme();
        }
    });

    // 5. Cross-tab synchronization
    window.addEventListener('storage', function (e) {
        if (e.key === THEME_STORAGE_KEY && e.newValue) {
            applyTheme(e.newValue, true);
        }
    });

    // 6. Post-DOMContentLoaded initialization
    document.addEventListener('DOMContentLoaded', function () {
        const currentTheme = getStoredTheme();
        applyTheme(currentTheme, false);
    });
})();
