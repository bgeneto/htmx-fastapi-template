# Data Grid System Documentation

## Overview

The fastapi-alpine-starter Data Grid is a **full-stack, reusable system** for displaying large datasets with server-side pagination, filtering, and sorting. It combines a backend introspection engine with a lightweight Alpine.js frontend.

### Three Core Components

1. **GridEngine** (`app/grid_engine.py`) - Backend data processor
2. **datagrid.js** (`static/js/datagrid.js`) - Alpine.js component
3. **_datagrid.html** (`templates/components/_datagrid.html`) - Reusable Tailwind template

## Architecture

### The "Universal Remote" Backend (GridEngine)

**Purpose**: Write the logic once, reuse infinitely.

The `GridEngine` uses Python introspection to examine any SQLModel table and automatically:
- Build parameterized SQL queries
- Apply type-aware filtering (string ILIKE, numeric exact match)
- Handle pagination and sorting
- Count total records

**Key Benefit**: Add a new column to your database tomorrow? The engine sees it automatically. No code changes needed.

```python
from app.grid_engine import GridEngine

@app.get("/api/contacts", response_model=PaginatedResponse[Contact])
async def get_contacts(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session)
):
    grid = GridEngine(session, Contact)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["name", "email"]  # Global search targets
    )
```

### The "Lightweight" Frontend (datagrid.js)

**Purpose**: Track user interaction without page refreshes.

The Alpine.js component manages:
- Which page the user is on
- Current sort column and direction
- Active filters
- Search query

When anything changes, it fetches only the 10-50 records needed, not the entire table.

```html
<div x-data="datagrid({
  apiUrl: '/api/contacts',
  columns: [
    { key: 'id', label: 'ID', width: 70, sortable: true },
    { key: 'name', label: 'Name', width: 200, sortable: true, filterable: true },
    { key: 'email', label: 'Email', width: 250, sortable: true, filterable: true }
  ]
})">
  <!-- grid template -->
</div>
```

### The "Server-Side" Strategy

Unlike client-side grids that load all data into the browser:

- **Browser holds**: Only 10-50 items at a time
- **Sorting**: Database does it (milliseconds) not JavaScript
- **Filtering**: SQL WHERE clauses, not client-side loops
- **Scaling**: Handles 10 rows or 10 million the same way

## Usage Guide

### Step 1: Define Your Model

```python
# app/models.py
class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    sku: str = Field(index=True)
    category: str = Field(index=True)
    price: float
    stock: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Step 2: Create the API Endpoint

```python
# app/main.py
from app.grid_engine import GridEngine, PaginatedResponse

@app.get("/api/products", response_model=PaginatedResponse[Product])
async def get_products(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session)
):
    grid = GridEngine(session, Product)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["name", "sku", "category"]
    )
```

### Step 3: Create a Page Template

```html
<!-- templates/pages/products.html -->
{% extends "_base.html" %}

{% block title %}{{ _('Products') }}{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto py-8">
  <h1 class="text-3xl font-bold mb-6">{{ _('Product Inventory') }}</h1>

  {% include "components/_datagrid.html" with context %}
</div>
{% endblock %}
```

Where the template context contains:

```python
@app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    return templates.TemplateResponse("pages/products.html", {
        "request": request,
        "api_url": "/api/products",
        "columns": [
            {"key": "id", "label": _("ID"), "width": 70, "sortable": True},
            {"key": "name", "label": _("Name"), "width": 200, "sortable": True, "filterable": True},
            {"key": "category", "label": _("Category"), "width": 150, "sortable": True, "filterable": True},
            {"key": "price", "label": _("Price"), "width": 120, "sortable": True},
            {"key": "stock", "label": _("Stock"), "width": 100, "sortable": True},
        ],
        "search_placeholder": _("Search by name, SKU, category...")
    })
```

## Query Parameters

The frontend automatically sends these parameters:

| Parameter | Type   | Example      | Purpose                   |
| --------- | ------ | ------------ | ------------------------- |
| `page`    | int    | `2`          | Current page (1-indexed)  |
| `limit`   | int    | `25`         | Items per page            |
| `q`       | string | `"Toyota"`   | Global search query       |
| `sort`    | string | `"price"`    | Column to sort by         |
| `dir`     | string | `"asc"`      | Sort direction (asc/desc) |
| `{field}` | string | `make=Honda` | Filter by column value    |

Example query:
```
GET /api/cars?page=2&limit=25&q=toyota&sort=price&dir=desc&make=Honda
```

## GridEngine API

### Constructor

```python
grid = GridEngine(session: AsyncSession, model: Type[T])
```

### Methods

#### `get_page()`

```python
result = await grid.get_page(
    request: Request,           # FastAPI Request object
    page: int = 1,              # Page number (1-indexed)
    limit: int = 10,            # Items per page
    sort_col: str = "id",       # Column to sort by
    sort_dir: str = "asc",      # "asc" or "desc"
    search_fields: List[str] = [] # Fields for global search
)
```

Returns: `PaginatedResponse[T]` containing:
- `items`: List of model instances for current page
- `total`: Total record count
- `page`: Current page number
- `limit`: Items per page
- `total_pages`: Calculated total pages

## Template Component

The `_datagrid.html` component requires these context variables:

| Variable             | Type           | Example                                   |
| -------------------- | -------------- | ----------------------------------------- |
| `api_url`            | str            | `/api/contacts`                           |
| `columns`            | list           | `[{"key": "name", "label": "Name", ...}]` |
| `search_placeholder` | str (optional) | `"Search contacts..."`                    |

Column definition object:
```python
{
    "key": str,              # Property name in data model
    "label": str,            # Display name in header
    "width": int,            # Width in pixels (default 150)
    "sortable": bool,        # Enable sort click (default False)
    "filterable": bool       # Show filter input (default False)
}
```

## Features

### Sorting
- Click column header to sort (if `sortable: true`)
- Click again to reverse direction
- Visual indicator (▲/▼) shows active sort

### Filtering
- Per-column filters (if `filterable: true`)
- Global search box targets `search_fields`
- Type-aware: strings use ILIKE, numbers exact match
- 300ms debounce to avoid excessive API calls

### Pagination
- Prev/Next buttons
- Configurable page size (10, 25, 50, 100)
- Shows "X-Y of Z" summary
- Automatically resets to page 1 on search/filter

### Responsive Design
- Horizontal scrolling on small screens
- Sticky header while scrolling
- Mobile-friendly controls

### Column Resizing
- Drag right edge of column header to resize
- Visual resize handle appears on hover
- Minimum width of 50px enforced

## Type-Aware Filtering

The GridEngine automatically detects column types:

```python
# String columns → ILIKE (partial match)
# GET /api/cars?make=toy
# Matches: "Toyota", "toy story", "toyotomi"

# Numeric columns → Exact match
# GET /api/cars?year=2023
# Matches: Only year=2023
```

Column types detected from SQLModel field definitions:
- `str`, `String`, `Text` → String filtering
- `int`, `float`, `Numeric` → Numeric filtering
- `bool`, `Boolean` → Boolean filtering
- `datetime` → Datetime filtering

## Performance Considerations

### Database Optimization

1. **Index key columns**:
   ```python
   name: str = Field(index=True)
   ```

2. **Filter by indexed columns** for best performance

3. **Limit search_fields** to 2-3 most important fields

4. **Use pagination** - default limit is 10, max recommended is 100

### Frontend Optimization

1. **Debounced search** (300ms) - prevents excessive API calls
2. **Lazy loading** - only fetches visible data
3. **No virtual DOM** - Alpine.js renders directly to DOM
4. **Direct Tailwind** - no CSS-in-JS overhead

## Error Handling

The component gracefully handles errors:

```javascript
try {
    const response = await fetch(`${apiUrl}?${params}`);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    // Update grid state
} catch (error) {
    console.error("Grid fetch error:", error);
    this.rows = [];
    this.total = 0;
}
```

## Internationalization

All labels and text use the `_()` translation function:

```html
<!-- In template -->
<div class="text-sm text-slate-600">
  {{ _('Managing') }} <span x-text="total"></span> {{ _('records') }}
</div>
```

When adding new grids, wrap user-facing strings in `_()` and run:
```bash
./translate.sh refresh
```

Then edit translation files and:
```bash
./translate.sh compile
```

## Advanced Examples

### Custom Formatting in Templates

```html
<td class="px-4 py-3">
  <span x-text="new Date(row.created_at).toLocaleDateString()"></span>
</td>
```

### Conditional Column Display

```html
<template x-if="currentUser.role === 'admin'">
  <th class="px-4 py-3">Actions</th>
</template>
```

### Custom Styling

Edit `static/css/input.css` to customize grid appearance:

```css
/* Custom grid colors */
@layer components {
  .datagrid-header {
    @apply bg-blue-50 border-blue-200;
  }

  .datagrid-row:hover {
    @apply bg-blue-100;
  }
}
```

## Troubleshooting

### Grid shows no data
- Check browser console for fetch errors
- Verify `api_url` matches actual endpoint
- Ensure endpoint returns correct `PaginatedResponse` format

### Filters not working
- Verify column name in `search_fields` list
- Check column has correct SQLModel type
- Use `filterable: true` in column definition

### Sorting not working
- Set `sortable: true` in column definition
- Verify column name matches database field name

### Performance issues
- Reduce `search_fields` list
- Add database indexes to commonly filtered columns
- Increase `limit` default if dataset is small
- Check database query performance with `EXPLAIN PLAN`

## Extending the GridEngine

### Custom Column Types

Override `GridEngine.get_page()` to handle custom types:

```python
class CustomGridEngine(GridEngine):
    async def get_page(self, request: Request, **kwargs):
        result = await super().get_page(request, **kwargs)
        # Custom post-processing
        return result
```

### Custom Filters

Pass additional filter logic before using GridEngine:

```python
query = select(Car)
query = query.where(Car.price > 30000)
grid = GridEngine(session, Car)
# GridEngine applies its own filters on top
```

## API Response Example

```json
{
  "items": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 245,
  "page": 1,
  "limit": 10,
  "total_pages": 25
}
```

## Summary

The Data Grid system achieves:

✅ **Total Design Freedom** - 100% Tailwind CSS, no plugin CSS to fight
✅ **Lazy Developer Workflow** - 5 minutes from model to working grid
✅ **Professional Performance** - Server-side processing scales to millions
✅ **Type Awareness** - Automatic filtering based on column types
✅ **i18n Support** - Built-in translation for all text
✅ **Responsive** - Works on mobile, tablet, desktop
✅ **Accessible** - Keyboard navigation, semantic HTML
