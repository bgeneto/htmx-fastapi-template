/**
 * Toast Notification System
 * 
 * A lightweight, dependency-free toast notification system using Tailwind CSS.
 * Supports internationalization (i18n) for UI elements.
 */

window.Toast = (function () {
    // Default configuration
    let config = {
        translations: {
            close: 'Close' // Default fallback
        },
        duration: 3000,
        containerId: 'toast-container'
    };

    /**
     * Initialize the toast system with custom options
     * @param {Object} options - Configuration options
     */
    function init(options = {}) {
        config = { ...config, ...options };
        if (options.translations) {
            config.translations = { ...config.translations, ...options.translations };
        }
        ensureContainer();
    }

    /**
     * Ensure the toast container exists in the DOM
     */
    function ensureContainer() {
        let container = document.getElementById(config.containerId);
        if (!container) {
            container = document.createElement('div');
            container.id = config.containerId;
            container.className = 'fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none'; // pointer-events-none allows clicking through the container area
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * Show a toast notification
     * @param {string} message - The message to display
     * @param {string} type - 'success', 'error', 'warning', 'info'
     */
    function show(message, type = 'info') {
        const container = ensureContainer();
        const toast = document.createElement('div');

        // Styling based on type
        let icon = '';
        let iconColorClass = '';
        let progressBarColorClass = '';
        let ringColorClass = '';

        switch (type) {
            case 'success':
                iconColorClass = 'text-green-500 bg-green-50 dark:bg-green-900/20';
                progressBarColorClass = 'bg-green-500';
                ringColorClass = 'ring-green-500/20';
                icon = `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
                break;
            case 'error':
                iconColorClass = 'text-red-500 bg-red-50 dark:bg-red-900/20';
                progressBarColorClass = 'bg-red-500';
                ringColorClass = 'ring-red-500/20';
                icon = `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>`;
                break;
            case 'warning':
                iconColorClass = 'text-yellow-500 bg-yellow-50 dark:bg-yellow-900/20';
                progressBarColorClass = 'bg-yellow-500';
                ringColorClass = 'ring-yellow-500/20';
                icon = `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`;
                break;
            default: // info
                iconColorClass = 'text-blue-500 bg-blue-50 dark:bg-blue-900/20';
                progressBarColorClass = 'bg-blue-500';
                ringColorClass = 'ring-blue-500/20';
                icon = `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
        }

        // Premium container styling
        // Fixed width (w-80 md:w-96) to prevent squashing
        // Ring for subtle border effect
        toast.className = `pointer-events-auto relative w-80 md:w-96 bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden transform transition-all duration-300 translate-y-full opacity-0 ring-1 ${ringColorClass}`;

        toast.innerHTML = `
            <div class="p-4 flex items-center gap-4">
                <div class="flex-shrink-0 inline-flex items-center justify-center w-10 h-10 rounded-full ${iconColorClass}">
                    ${icon}
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-normal text-gray-900 dark:text-white leading-5 pr-6">
                        ${message}
                    </p>
                </div>
                <button type="button" class="absolute top-3 right-3 text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 rounded-md p-1" aria-label="${config.translations.close}">
                    <span class="sr-only">${config.translations.close}</span>
                    <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                    </svg>
                </button>
            </div>
            <!-- Progress Bar -->
            <div class="absolute bottom-0 left-0 h-1 w-full bg-gray-100 dark:bg-gray-700">
                <div class="h-full ${progressBarColorClass} transition-all ease-linear" style="width: 100%; transition-duration: ${config.duration}ms;"></div>
            </div>
        `;

        // Close button handler
        const closeBtn = toast.querySelector('button');
        closeBtn.addEventListener('click', () => removeToast(toast));

        container.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-full', 'opacity-0');
            // Start progress bar animation
            const progressBar = toast.querySelector('.absolute.bottom-0 > div');
            if (progressBar) {
                // Force reflow to ensure transition triggers
                void progressBar.offsetWidth;
                progressBar.style.width = '0%';
            }
        });

        // Auto remove
        setTimeout(() => {
            removeToast(toast);
        }, config.duration);
    }

    function removeToast(toast) {
        if (!toast.parentElement) return;

        toast.classList.add('opacity-0', 'translate-y-full');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 300);
    }

    return {
        init,
        show
    };
})();

// Backward compatibility
window.showToast = window.Toast.show;
