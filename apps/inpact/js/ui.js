// CycleBoard UI Utilities Module
// Handles toasts, modals, and common UI elements

const UI = {
  // Color class mappings for Tailwind (prevents purging of dynamic classes)
  colorClasses: {
    blue: {
      bg: 'bg-blue-500',
      bgLight: 'bg-blue-100',
      bgDark: 'dark:bg-blue-900/30',
      text: 'text-blue-500',
      textDark: 'dark:text-blue-400'
    },
    green: {
      bg: 'bg-green-500',
      bgLight: 'bg-green-100',
      bgDark: 'dark:bg-green-900/30',
      text: 'text-green-500',
      textDark: 'dark:text-green-400'
    },
    purple: {
      bg: 'bg-purple-500',
      bgLight: 'bg-purple-100',
      bgDark: 'dark:bg-purple-900/30',
      text: 'text-purple-500',
      textDark: 'dark:text-purple-400'
    },
    orange: {
      bg: 'bg-orange-500',
      bgLight: 'bg-orange-100',
      bgDark: 'dark:bg-orange-900/30',
      text: 'text-orange-500',
      textDark: 'dark:text-orange-400'
    },
    yellow: {
      bg: 'bg-yellow-500',
      bgLight: 'bg-yellow-100',
      bgDark: 'dark:bg-yellow-900/30',
      text: 'text-yellow-500',
      textDark: 'dark:text-yellow-400'
    },
    red: {
      bg: 'bg-red-500',
      bgLight: 'bg-red-100',
      bgDark: 'dark:bg-red-900/30',
      text: 'text-red-500',
      textDark: 'dark:text-red-400'
    },
    amber: {
      bg: 'bg-amber-500',
      bgLight: 'bg-amber-100',
      bgDark: 'dark:bg-amber-900/30',
      text: 'text-amber-500',
      textDark: 'dark:text-amber-400'
    }
  },

  // Get color classes by name - prevents Tailwind purging
  getColorClass(color, type = 'bg') {
    const colorMap = this.colorClasses[color];
    return colorMap ? colorMap[type] : '';
  },

  // Sanitize HTML to prevent XSS attacks
  sanitize(input) {
    if (input === null || input === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(input);
    return div.innerHTML;
  },

  showToast(title, description, type = 'info') {
    const colors = {
      success: 'bg-green-50 border-green-200 text-green-800 dark:bg-green-900/20 dark:border-green-800 dark:text-green-300',
      error: 'bg-red-50 border-red-200 text-red-800 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300',
      warning: 'bg-yellow-50 border-yellow-200 text-yellow-800 dark:bg-yellow-900/20 dark:border-yellow-800 dark:text-yellow-300',
      info: 'bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-300'
    };

    const toast = document.createElement('div');
    toast.className = `toast border rounded-lg shadow-lg p-4 min-w-[300px] ${colors[type]}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');
    toast.innerHTML = `
      <div class="flex items-center gap-3">
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}" aria-hidden="true"></i>
        <div>
          <div class="font-semibold">${UI.sanitize(title)}</div>
          ${description ? `<div class="text-sm opacity-80 mt-1">${UI.sanitize(description)}</div>` : ''}
        </div>
      </div>
    `;

    const container = document.getElementById('toast-container');
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  },

  // Note: content parameter should only contain trusted HTML built by the app
  // User data within content must be sanitized using UI.sanitize() before inclusion
  showModal(content) {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop fixed inset-0 z-50 flex items-center justify-center fade-in';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');

    // Create backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'fixed inset-0 bg-black/50';
    backdrop.setAttribute('aria-hidden', 'true');
    backdrop.onclick = () => UI.closeModal();

    // Create content container
    const contentContainer = document.createElement('div');
    contentContainer.className = 'relative z-50 bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-auto slide-up';
    contentContainer.innerHTML = content;

    // Set aria-labelledby if there's an h2 heading
    const heading = contentContainer.querySelector('h2');
    if (heading) {
      const headingId = 'modal-heading-' + Date.now();
      heading.id = headingId;
      modal.setAttribute('aria-labelledby', headingId);
    }

    modal.appendChild(backdrop);
    modal.appendChild(contentContainer);
    document.getElementById('modal-container').appendChild(modal);
    document.body.style.overflow = 'hidden';

    // Store previously focused element to restore on close
    UI._previouslyFocused = document.activeElement;

    // Focus first focusable element for accessibility
    const focusable = contentContainer.querySelector('input, button, select, textarea');
    if (focusable) {
      setTimeout(() => focusable.focus(), 100);
    }

    // Add escape key listener
    document.addEventListener('keydown', UI._escapeHandler);
  },

  closeModal() {
    const container = document.getElementById('modal-container');
    container.innerHTML = '';
    document.body.style.overflow = '';
    // Remove escape key listener
    document.removeEventListener('keydown', UI._escapeHandler);
    // Restore focus to previously focused element
    if (UI._previouslyFocused && UI._previouslyFocused.focus) {
      UI._previouslyFocused.focus();
      UI._previouslyFocused = null;
    }
  },

  // Store reference to previously focused element
  _previouslyFocused: null,

  // Escape key handler for modals
  _escapeHandler(e) {
    if (e.key === 'Escape') {
      UI.closeModal();
    }
  },

  renderProgressRing(percentage, size = 40, stroke = 4) {
    const radius = (size - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percentage / 100) * circumference;

    return `
      <svg width="${size}" height="${size}" class="progress-ring">
        <circle
          class="progress-ring__circle"
          stroke="#e5e7eb"
          stroke-width="${stroke}"
          fill="transparent"
          r="${radius}"
          cx="${size / 2}"
          cy="${size / 2}"
        />
        <circle
          class="progress-ring__circle"
          stroke="${percentage >= 70 ? '#10B981' : percentage >= 40 ? '#F59E0B' : '#EF4444'}"
          stroke-width="${stroke}"
          fill="transparent"
          r="${radius}"
          cx="${size / 2}"
          cy="${size / 2}"
          stroke-dasharray="${circumference}"
          stroke-dashoffset="${offset}"
        />
        <text
          x="50%"
          y="50%"
          text-anchor="middle"
          dy="0.3em"
          class="text-xs font-bold dark:fill-white"
          fill="currentColor"
        >${percentage}%</text>
      </svg>
    `;
  },

  updateDateDisplay() {
    const dateEl = document.getElementById('date-display');
    if (dateEl) {
      const now = new Date();
      const options = { weekday: 'short', month: 'short', day: 'numeric' };
      dateEl.textContent = now.toLocaleDateString('en-US', options);
    }
  },

  // Loading overlay for async operations
  showLoading(message = 'Loading...') {
    // Remove existing loader if present
    UI.hideLoading();

    const loader = document.createElement('div');
    loader.id = 'loading-overlay';
    loader.className = 'fixed inset-0 z-[100] flex items-center justify-center bg-black/30';
    loader.setAttribute('role', 'status');
    loader.setAttribute('aria-live', 'polite');
    loader.innerHTML = `
      <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 flex items-center gap-4">
        <div class="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent" aria-hidden="true"></div>
        <span class="text-lg font-medium dark:text-white">${UI.sanitize(message)}</span>
      </div>
    `;
    document.body.appendChild(loader);
  },

  hideLoading() {
    const loader = document.getElementById('loading-overlay');
    if (loader) {
      loader.remove();
    }
  },

  // Show inline loading spinner (for buttons, etc.)
  spinnerHtml(size = 'md') {
    const sizes = {
      sm: 'h-4 w-4 border-2',
      md: 'h-6 w-6 border-2',
      lg: 'h-8 w-8 border-4'
    };
    return `<div class="animate-spin rounded-full ${sizes[size] || sizes.md} border-current border-t-transparent" aria-hidden="true"></div>`;
  }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = UI;
}
