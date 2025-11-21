/**
 * Alpine.js Data Grid Component
 *
 * A lightweight, reactive data grid for server-side pagination, filtering, and sorting.
 * Works seamlessly with the GridEngine backend.
 *
 * Usage:
 *   <div x-data="datagrid({
 *     apiUrl: '/api/contacts',
 *     columns: [
 *       { key: 'id', label: 'ID', width: 70, sortable: true },
 *       { key: 'name', label: 'Name', width: 200, sortable: true, filterable: true },
 *       { key: 'email', label: 'Email', width: 250, sortable: true, filterable: true }
 *     ]
 *   })">
 *     <!-- grid content -->
 *   </div>
 */

document.addEventListener("alpine:init", () => {
  Alpine.data("datagrid", ({ columns, apiUrl }) => ({
    // State
    rows: [],
    cols: columns || [],
    search: "",
    filters: {},
    sortCol: "id",
    sortAsc: true,
    errors: {}, // Validation errors

    // Pagination state
    page: 1,
    pageInput: 1,
    limit: 10,
    total: 0,
    lastPage: 1,
    from: 0,
    to: 0,
    loading: false,

    // Column resizing state
    resizingCol: null,
    startX: 0,
    startWidth: 0,

    // Modal state for CRUD operations
    showModal: false,
    modalMode: 'add', // 'add', 'edit', 'delete'
    currentRow: {},

    init() {
      // Initialize filter objects for filterable columns
      this.cols.forEach((col) => {
        if (col.filterable) {
          this.filters[col.key] = "";
        }
      });

      // Fetch initial data
      this.fetchData();

      // Watch pagination - sync pageInput with page changes and fetch
      this.$watch("page", (val) => {
        this.pageInput = val;
        this.fetchData();
      });
      // Watch limit - reset page and fetch data
      this.$watch("limit", () => {
        this.page = 1;
        this.fetchData();
      });

      // Watch sort
      this.$watch("sortCol", () => this.fetchData());
      this.$watch("sortAsc", () => this.fetchData());

      // Debounced watchers for search and filters
      let searchTimeout;
      const debouncedSearch = () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
          this.page = 1;
          this.fetchData(); // Trigger data fetch after debouncing
        }, 300);
      };

      this.$watch("search", debouncedSearch);
      this.$watch("filters", debouncedSearch, { deep: true });
    },

    async fetchData() {
      this.loading = true;

      // Build query string with pagination, search, sort, and filters
      const params = new URLSearchParams({
        page: this.page,
        limit: this.limit,
        q: this.search,
        sort: this.sortCol,
        dir: this.sortAsc ? "asc" : "desc",
        ...this.filters,
      });

      try {
        const response = await fetch(`${apiUrl}?${params}`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // Update grid state from response
        this.rows = data.items || [];
        this.total = data.total || 0;
        this.lastPage = data.total_pages || 1;

        // Calculate "Showing X to Y of Z"
        this.from =
          this.total === 0 ? 0 : (this.page - 1) * this.limit + 1;
        this.to = Math.min(this.page * this.limit, this.total);
      } catch (error) {
        console.error("Grid fetch error:", error);
        this.rows = [];
        this.total = 0;
      } finally {
        this.loading = false;
      }
    },

    /**
     * Toggle sort direction or change sort column
     */
    sortBy(key) {
      if (this.sortCol === key) {
        this.sortAsc = !this.sortAsc;
      } else {
        this.sortCol = key;
        this.sortAsc = true;
      }
    },

    /**
     * Pagination controls
     */
    nextPage() {
      if (this.page < this.lastPage) {
        this.page++;
      }
    },

    prevPage() {
      if (this.page > 1) {
        this.page--;
      }
    },

    gotoPage(p) {
      const pageNum = parseInt(p);
      if (pageNum >= 1 && pageNum <= this.lastPage) {
        this.page = pageNum;
      }
    },

    /**
     * Column resizing (drag right edge to resize)
     */
    startResize(event, colKey) {
      event.preventDefault();

      const resizingColumn = this.cols.find((c) => c.key === colKey);
      if (!resizingColumn) return;

      this.resizingCol = resizingColumn;
      this.startX = event.clientX;
      this.startWidth = resizingColumn.width || 150;

      const onMove = (e) => {
        if (!this.resizingCol) return;
        const delta = e.clientX - this.startX;
        this.resizingCol.width = Math.max(50, this.startWidth + delta);
      };

      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        this.resizingCol = null;
      };

      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },

    /**
     * Clear all filters
     */
    clearFilters() {
      this.search = "";
      Object.keys(this.filters).forEach(key => {
        this.filters[key] = "";
      });
      // Reset to first page and fetch immediately (no debounce needed for clear)
      this.page = 1;
      this.fetchData();
    },

    /**
     * CRUD Modal Actions
     */
    openAddModal() {
      this.modalMode = 'add';
      this.currentRow = {};
      this.errors = {};
      this.showModal = true;
    },

    openEditModal(row) {
      this.modalMode = 'edit';
      this.currentRow = { ...row };
      this.errors = {};
      this.showModal = true;
    },

    openDeleteModal(row) {
      this.modalMode = 'delete';
      this.currentRow = { ...row };
      this.errors = {};
      this.showModal = true;
    },

    closeModal() {
      this.showModal = false;
      this.currentRow = {};
      this.errors = {};
    },

    async saveRow() {
      this.errors = {}; // Clear previous errors
      console.log('[DATAGRID] Saving row:', this.currentRow);

      try {
        const url = this.modalMode === 'add'
          ? apiUrl
          : `${apiUrl}/${this.currentRow.id}`;

        const method = this.modalMode === 'add' ? 'POST' : 'PUT';
        const action = this.modalMode === 'add' ? 'added' : 'updated';

        // Exclude timestamp fields that should not be updated
        const payload = { ...this.currentRow };
        delete payload.created_at;
        delete payload.updated_at;

        console.log('[DATAGRID] Sending payload:', payload);

        const response = await fetch(url, {
          method: method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        console.log('[DATAGRID] Response status:', response.status);

        if (response.ok) {
          this.closeModal();
          this.fetchData();
          this.showToast(`Record ${action} successfully`, 'success');
        } else {
          const errorText = await response.text();
          console.error('[DATAGRID] Save failed with response:', errorText);

          let errorMessage = `Failed to ${action} record`;
          let hasFieldErrors = false;

          try {
            const errorData = JSON.parse(errorText);
            console.log('[DATAGRID] Parsed error data:', errorData);

            // Handle 422 Validation Errors from FastAPI/Pydantic
            if (response.status === 422 && errorData.detail) {
              if (Array.isArray(errorData.detail)) {
                console.log('[DATAGRID] Processing validation errors:', errorData.detail);

                errorData.detail.forEach(err => {
                  console.log('[DATAGRID] Processing error:', err);
                  // err.loc is usually ["body", "field_name"] or just ["field_name"]
                  const field = err.loc[err.loc.length - 1];

                  // Make error message more user-friendly
                  let message = err.msg;
                  if (err.type === 'greater_than') {
                    const limit = err.ctx?.gt || 0;
                    message = `Value must be greater than ${limit}`;
                  } else if (err.type === 'value_error.missing') {
                    message = 'This field is required';
                  } else if (err.type === 'type_error.integer') {
                    message = 'Must be a valid number';
                  } else if (err.type === 'string_too_short') {
                    message = 'This field cannot be empty';
                  }

                  this.errors[field] = message;
                  console.log(`[DATAGRID] Set error for field '${field}':`, message);
                  hasFieldErrors = true;
                });

                if (hasFieldErrors) {
                  errorMessage = "Please fix the validation errors below.";
                }
              } else if (typeof errorData.detail === 'string') {
                errorMessage = errorData.detail;
              }
            } else if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch (e) {
            console.error('[DATAGRID] Failed to parse error response:', e);
            // Keep default error message
          }

          console.log('[DATAGRID] Final errors object:', this.errors);
          console.log('[DATAGRID] Final error message:', errorMessage);
          this.showToast(errorMessage, 'error');
        }
      } catch (error) {
        console.error('[DATAGRID] Network error:', error);
        this.showToast(`Network error while saving record`, 'error');
      }
    },

    async deleteRow() {
      try {
        const response = await fetch(`${apiUrl}/${this.currentRow.id}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          this.closeModal();
          this.fetchData();

          // Show success toast
          this.showToast('Record deleted successfully', 'success');
        } else {
          const errorText = await response.text();
          console.error('Delete failed:', errorText);

          let errorMessage = 'Failed to delete record';
          try {
            const errorData = JSON.parse(errorText);
            errorMessage = errorData.detail || errorMessage;
          } catch (e) {
            // Not JSON, use text
          }

          this.showToast(errorMessage, 'error');
        }
      } catch (error) {
        console.error('Delete error:', error);
        this.showToast('Network error while deleting record', 'error');
      }
    },

    /**
     * Show a toast notification
     */
    showToast(message, type = 'info') {
      console.log(`[TOAST ${type.toUpperCase()}]: ${message}`); // Always log for debugging

      // Try to use the toast system from _base.html if available
      if (typeof window.showToast === 'function') {
        console.log('Using window.showToast');
        window.showToast(message, type);
      } else {
        console.log('Using fallback toast notification');

        // Create a more visible fallback notification
        const notification = document.createElement('div');
        notification.style.cssText = `
          position: fixed;
          top: 20px;
          right: 20px;
          background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
          color: white;
          padding: 12px 16px;
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          font-size: 14px;
          font-weight: 500;
          z-index: 10000;
          max-width: 300px;
          word-wrap: break-word;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        // Ensure the notification is visible by scrolling it into view if needed
        setTimeout(() => notification.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 100);

        // Remove after 5 seconds with fade out
        setTimeout(() => {
          notification.style.transition = 'opacity 0.3s ease-out';
          notification.style.opacity = '0';
          setTimeout(() => {
            if (notification.parentNode) {
              notification.parentNode.removeChild(notification);
            }
          }, 300);
        }, 5000);

        // Add click to dismiss
        notification.addEventListener('click', () => {
          if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
          }
        });
      }
    },
  }));
});
