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
 *     ],
 *     i18n: {
 *       valueGreaterEqual: "Value must be greater than or equal to {0}",
 *       // ... other translations
 *     }
 *   })">
 *     <!-- grid content -->
 *   </div>
 */

document.addEventListener("alpine:init", () => {
  Alpine.data("datagrid", ({ columns, apiUrl, i18n = {} }) => ({
    // State
    rows: [],
    cols: columns || [],
    search: "",
    filters: {},
    sortCol: "id",
    sortAsc: true,
    errors: {}, // Validation errors
    i18n: i18n, // Translation strings from template

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

    /**
     * Translate validation error based on type and context
     */
    translateError(errorType, context = {}, originalMsg = '') {
      const templates = {
        'greater_than_equal': this.i18n.valueGreaterEqual || 'Value must be greater than or equal to {0}',
        'greater_than': this.i18n.valueGreater || 'Value must be greater than {0}',
        'less_than_equal': this.i18n.valueLessEqual || 'Value must be less than or equal to {0}',
        'less_than': this.i18n.valueLess || 'Value must be less than {0}',
        'value_error.missing': this.i18n.fieldRequired || 'This field is required',
        'missing': this.i18n.fieldRequired || 'This field is required',
        'type_error.integer': this.i18n.validNumber || 'Must be a valid number',
        'int_type': this.i18n.validInteger || 'Must be a valid integer',
        'string_too_short': this.i18n.minLength || 'Must be at least {0} character(s)',
        'string_too_long': this.i18n.maxLength || 'Must be at most {0} character(s)',
        'string_type': this.i18n.validText || 'Must be a valid text',
        'value_error': this.i18n.invalidValue || 'Invalid value',
      };

      const template = templates[errorType];
      if (!template) {
        return originalMsg || (this.i18n.validationError || 'Validation error');
      }

      // Replace {0} with the appropriate context value
      let message = template;
      if (context.ge !== undefined) message = message.replace('{0}', context.ge);
      else if (context.gt !== undefined) message = message.replace('{0}', context.gt);
      else if (context.le !== undefined) message = message.replace('{0}', context.le);
      else if (context.lt !== undefined) message = message.replace('{0}', context.lt);
      else if (context.min_length !== undefined) message = message.replace('{0}', context.min_length);
      else if (context.max_length !== undefined) message = message.replace('{0}', context.max_length);

      return message;
    },

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
        const response = await axios.get(`${apiUrl}?${params}`);
        const data = response.data;

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

        const action = this.modalMode === 'add' ? 'added' : 'updated';

        // Exclude timestamp fields that should not be updated
        const payload = { ...this.currentRow };
        delete payload.created_at;
        delete payload.updated_at;

        console.log('[DATAGRID] Sending payload:', payload);

        let response;
        if (this.modalMode === 'add') {
          response = await axios.post(url, payload);
        } else {
          response = await axios.put(url, payload);
        }

        console.log('[DATAGRID] Response status:', response.status);

        // Success case
        this.closeModal();
        this.fetchData();
        const successKey = action === 'added' ? 'recordAddSuccess' : 'recordUpdateSuccess';
        const successMessage = this.i18n[successKey] || `Record ${action} successfully`;
        this.showToast(successMessage, 'success');

      } catch (error) {
        console.error('[DATAGRID] Save failed with error:', error);

        const errorKey = this.modalMode === 'add' ? 'recordAddFailed' : 'recordUpdateFailed';
        let errorMessage = this.i18n[errorKey] || `Failed to ${this.modalMode === 'add' ? 'add' : 'update'} record`;
        let hasFieldErrors = false;

        // Handle Axios error response
        if (error.response) {
          const status = error.response.status;
          const errorData = error.response.data;

          console.log('[DATAGRID] Error response data:', errorData);

          // Handle 422 Validation Errors from FastAPI/Pydantic
          if (status === 422 && errorData.detail) {
            if (Array.isArray(errorData.detail)) {
              console.log('[DATAGRID] Processing validation errors:', errorData.detail);

              errorData.detail.forEach(err => {
                console.log('[DATAGRID] Processing error:', err);
                // err.loc is usually ["body", "field_name"] or just ["field_name"]
                const field = err.loc[err.loc.length - 1];

                // Translate error message using i18n from template
                const message = this.translateError(err.type, err.ctx || {}, err.msg);

                this.errors[field] = message;
                console.log(`[DATAGRID] Set error for field '${field}':`, message);
                hasFieldErrors = true;
              });

              if (hasFieldErrors) {
                // Use translated error message from i18n
                errorMessage = this.i18n.fixErrors || "Please fix the validation errors below.";
              }
            } else if (typeof errorData.detail === 'string') {
              errorMessage = errorData.detail;
            }
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } else if (error.request) {
          // Network error (no response received)
          errorMessage = this.i18n.networkError || 'Network error - no response from server';
        } else {
          // Other error (request setup, etc.)
          errorMessage = error.message || (this.i18n.unknownError || 'Unknown error occurred');
        }

        console.log('[DATAGRID] Final errors object:', this.errors);
        console.log('[DATAGRID] Final error message:', errorMessage);
        this.showToast(errorMessage, 'error');
      }
    },

    async deleteRow() {
      try {
        await axios.delete(`${apiUrl}/${this.currentRow.id}`);

        // Success case
        this.closeModal();
        this.fetchData();
        const successMessage = this.i18n.recordDeleteSuccess || 'Record deleted successfully';
        this.showToast(successMessage, 'success');

      } catch (error) {
        console.error('Delete error:', error);

        let errorMessage = this.i18n.recordDeleteFailed || 'Failed to delete record';

        // Handle Axios error response
        if (error.response) {
          const errorData = error.response.data;
          console.log('Delete failed with response:', errorData);

          if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } else if (error.request) {
          // Network error (no response received)
          errorMessage = this.i18n.networkError || 'Network error - no response from server';
        } else {
          // Other error (request setup, etc.)
          errorMessage = error.message || (this.i18n.unknownError || 'Unknown error occurred');
        }

        this.showToast(errorMessage, 'error');
      }
    },

    /**
     * Show a toast notification
     */
    /**
     * Show a toast notification
     */
    showToast(message, type = 'info') {
      console.log(`[TOAST ${type.toUpperCase()}]: ${message}`); // Always log for debugging

      // Use the global toast system
      if (typeof window.showToast === 'function') {
        window.showToast(message, type);
      } else {
        console.warn('Toast system not initialized. Message:', message);
        alert(`${type.toUpperCase()}: ${message}`); // Last resort fallback
      }
    },
  }));
});
