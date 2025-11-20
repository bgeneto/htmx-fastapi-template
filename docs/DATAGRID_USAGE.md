# Data Grid Usage

The `GridEngine` provides universal, server-side pagination, filtering, and sorting for any SQLModel table.

## Quick Start (3 Steps)

### 1. Create API Endpoint

```python
from app.grid_engine import GridEngine, PaginatedResponse
from app.models import YourModel

@app.get("/api/items", response_model=PaginatedResponse[YourModel])
async def get_items(
    request: Request,
    page: int = 1,
    limit: int = 10,
    sort: str = "id",
    dir: str = "asc",
    session: AsyncSession = Depends(get_session)
):
    grid = GridEngine(session, YourModel)
    return await grid.get_page(
        request=request,
        page=page,
        limit=limit,
        sort_col=sort,
        sort_dir=dir,
        search_fields=["field1", "field2"]  # for global search
    )
```

### 2. Create Page Route

```python
@app.get("/items", response_class=HTMLResponse)
async def items_page(request: Request):
    return templates.TemplateResponse("pages/items.html", {
        "request": request,
        "api_url": "/api/items",
        "columns": [
            {"key": "id", "label": "ID", "width": 70, "sortable": True},
            {"key": "name", "label": "Name", "width": 200, "sortable": True, "filterable": True},
            {"key": "price", "label": "Price", "width": 120, "sortable": True},
        ],
        "search_placeholder": "Search..."
    })
```

### 3. Create Template

```html
{% extends "_base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-8">
    <h1 class="text-3xl font-bold mb-6">Items</h1>
    {% include "components/_datagrid.html" with context %}
</div>
{% endblock %}
```

## Features

- **Pagination**: 10, 25, 50, 100 items per page
- **Global Search**: Search across multiple fields
- **Column Filters**: Per-column filtering
- **Sorting**: Click headers to sort ascending/descending
- **Responsive**: Mobile, tablet, desktop
- **Type-aware**: Strings use ILIKE, numbers use exact match

## Example: Cars Grid

See `/admin/cars` for a working example with 500 seeded cars.

Query examples:
```
GET /api/admin/cars?page=1&limit=25
GET /api/admin/cars?q=toyota
GET /api/admin/cars?make=Honda&year=2023
GET /api/admin/cars?sort=price&dir=desc
```

## Configuration

Column definition:
```python
{
    "key": "field_name",        # required
    "label": "Display Name",    # required
    "width": 150,               # optional, default 150px
    "sortable": True,           # optional
    "filterable": True          # optional
}
```

## Performance

- Server-side pagination (only fetches visible rows)
- Optimized database queries
- Debounced search (300ms)
- Scales to millions of records
