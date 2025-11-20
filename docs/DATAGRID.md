# Data Grid System

## Overview
Reusable server-side data grid with Alpine.js frontend and FastAPI backend.

## Features
- Server-side pagination, sorting, filtering
- Dark mode support
- Column resizing
- CRUD operations via modal dialogs
- Type-aware search (string ILIKE, numeric exact match)
- Auto-introspection of SQLModel tables

## Usage

### 1. Backend (FastAPI)
```python
from app.grid_engine import GridEngine, PaginatedResponse
from app.models import Car

@app.get("/api/admin/cars", response_model=PaginatedResponse[Car])
async def get_cars(request: Request, page: int = 1, limit: int = 10, 
                    sort: str = "id", dir: str = "asc",
                    session: AsyncSession = Depends(get_session)):
    grid = GridEngine(session, Car)
    return await grid.get_page(request, page, limit, sort, dir, 
                                search_fields=["make", "model"])
```

### 2. Frontend (Template)
```html
<div x-data="datagrid({
    apiUrl: '/api/admin/cars',
    columns: [
        {key: 'id', label: 'ID', width: 70, sortable: true},
        {key: 'make', label: 'Make', width: 150, sortable: true, filterable: true},
        {key: 'actions', label: 'Actions', width: 100}
    ]
})">
    {% include "components/_datagrid_grid.html" %}
</div>
```

## Files
- `app/grid_engine.py` - Backend engine
- `static/js/datagrid.js` - Alpine.js component
- `templates/components/_datagrid_grid.html` - Grid UI template
