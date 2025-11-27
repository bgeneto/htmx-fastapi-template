/**
 * Global Initialization Script
 * Handles theme toggling, sidebar resizing, and common utilities
 *
 * Note: i18n translations for datagrid and toast are initialized in _header.html
 * This ensures translations are available BEFORE Alpine.js components initialize
 */

/**
 * DOMContentLoaded - Initialize theme UI
 */
document.addEventListener('DOMContentLoaded', function () {
    // Update icons to match the initial theme state
    const isDark = document.documentElement.classList.contains('dark');
    updateThemeIcons(isDark);
});

/**
 * Toggle theme between light and dark mode
 * @function window.toggleTheme
 */
window.toggleTheme = function () {
    const html = document.documentElement;
    const isCurrentlyDark = html.classList.contains('dark');

    // Toggle the dark class on html element
    if (isCurrentlyDark) {
        html.classList.remove('dark');
        localStorage.setItem('theme', 'light');
    } else {
        html.classList.add('dark');
        localStorage.setItem('theme', 'dark');
    }

    // Update icons
    updateThemeIcons(!isCurrentlyDark);
};

/**
 * Update theme toggle icons
 * @param {boolean} isDark - Whether dark mode is enabled
 */
function updateThemeIcons(isDark) {
    document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
        const sunIcon = btn.querySelector('[data-theme-sun]');
        const moonIcon = btn.querySelector('[data-theme-moon]');
        if (sunIcon && moonIcon) {
            if (isDark) {
                sunIcon.classList.remove('hidden');
                moonIcon.classList.add('hidden');
            } else {
                moonIcon.classList.remove('hidden');
                sunIcon.classList.add('hidden');
            }
        }
    });
}

/**
 * Alpine.js resizable sidebar component factory
 * @param {Object} config - Configuration object
 * @returns {Object} Alpine component state and methods
 */
function resizableSidebar({ key, defaultWidth, minWidth, maxWidth }) {
    return {
        sidebarWidth: defaultWidth,
        collapsed: false,
        dragging: false,
        storageKey: key,
        collapsedKey: key + '_isCollapsed',

        init() {
            // Restore collapsed state
            const isCollapsed = localStorage.getItem(this.collapsedKey) === 'true';
            this.collapsed = isCollapsed;

            // Restore width
            const saved = localStorage.getItem(this.storageKey);
            let px = defaultWidth;

            if (saved) {
                px = this.clamp(parseInt(saved, 10));
            }

            if (this.collapsed) {
                this._saved = px; // Remember the expanded width
                this.sidebarWidth = 56;
            } else {
                this.sidebarWidth = px;
            }

            document.documentElement.style.setProperty('--sidebar-width', this.sidebarWidth + 'px');
        },

        clamp(w) {
            return Math.min(maxWidth, Math.max(minWidth, Math.round(w)));
        },

        startDrag(e) {
            this.dragging = true;
            this.startX = e.clientX;
            this.startWidth = this.sidebarWidth;

            const moveHandler = this.onMove.bind(this);
            const upHandler = this.stopDrag.bind(this);

            window.addEventListener('pointermove', moveHandler);
            window.addEventListener('pointerup', upHandler);
            window.addEventListener('pointercancel', upHandler);

            this._moveHandler = moveHandler;
            this._upHandler = upHandler;
        },

        onMove(e) {
            if (!this.dragging) return;

            const dx = e.clientX - this.startX;
            const newWidth = this.clamp(this.startWidth + dx);

            this.sidebarWidth = newWidth;
            document.documentElement.style.setProperty('--sidebar-width', newWidth + 'px');

            localStorage.setItem(this.storageKey, newWidth);
        },

        stopDrag() {
            if (!this.dragging) return;
            this.dragging = false;

            window.removeEventListener('pointermove', this._moveHandler);
            window.removeEventListener('pointerup', this._upHandler);
            window.removeEventListener('pointercancel', this._upHandler);
        },

        toggleCollapse() {
            this.collapsed = !this.collapsed;
            localStorage.setItem(this.collapsedKey, this.collapsed);

            if (this.collapsed) {
                this._saved = this.sidebarWidth;
                this.sidebarWidth = 56;
                // Do NOT save the collapsed width (56) to the main storageKey
                // so we preserve the user's preferred expanded width
            } else {
                // Restore width
                let targetWidth = this._saved;

                // Fallback to storage if _saved is missing
                if (!targetWidth) {
                    const saved = localStorage.getItem(this.storageKey);
                    if (saved) targetWidth = parseInt(saved, 10);
                }

                this.sidebarWidth = this.clamp(targetWidth ?? defaultWidth);
                // Save the restored width to be sure
                localStorage.setItem(this.storageKey, this.sidebarWidth);
            }

            document.documentElement.style.setProperty('--sidebar-width', this.sidebarWidth + 'px');
        },

        handleKeydown(e) {
            const step = 8;
            if (e.key === 'ArrowLeft') this.sidebarWidth = this.clamp(this.sidebarWidth - step);
            if (e.key === 'ArrowRight') this.sidebarWidth = this.clamp(this.sidebarWidth + step);
            if (e.key === 'Home') this.sidebarWidth = minWidth;
            if (e.key === 'End') this.sidebarWidth = maxWidth;

            document.documentElement.style.setProperty('--sidebar-width', this.sidebarWidth + 'px');
            localStorage.setItem(this.storageKey, this.sidebarWidth);
        }
    };
}

// Export for Alpine.js
window.resizableSidebar = resizableSidebar;
