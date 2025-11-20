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
    // Table state
    rows: [],
    cols: columns || [],
    search: "",
    filters: {},
    sortCol: "id",
    sortAsc: true,

    // Pagination state
    page: 1,
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

    init() {
      // Initialize filter objects for filterable columns
      this.cols.forEach((col) => {
        if (col.filterable) {
          this.filters[col.key] = "";
        }
      });

      // Fetch initial data
      this.fetchData();

      // Watch pagination
      this.$watch("page", () => this.fetchData());
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
          this.fetchData();
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
      if (p >= 1 && p <= this.lastPage) {
        this.page = p;
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
  }));
});
