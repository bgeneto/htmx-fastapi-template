"""
Sidebar menu configuration and filtering logic.

This module provides a declarative way to define sidebar menu items
with role-based access control, i18n support, and nested submenus.

Usage:
    Edit get_menu_config() to add/remove/reorganize menu items.
    The template will automatically render based on this configuration.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .i18n import gettext as _
from .models.user import UserRole

if TYPE_CHECKING:
    from .models import User


# Role hierarchy for permission checks (higher number = more access)
ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.PENDING: 0,
    UserRole.USER: 1,
    UserRole.MODERATOR: 2,
    UserRole.ADMIN: 3,
}


@dataclass
class MenuItem:
    """
    Represents a single menu item in the sidebar.

    Attributes:
        key: Unique identifier for the item (used for i18n lookup and localStorage)
        icon: FontAwesome icon name WITHOUT prefix (e.g., "fa-book", not "fa-solid fa-book")
              The template handles switching between fa-regular and fa-solid states
        route: URL path for the link. Use None for parent-only items with children.
        roles: List of roles that can see this item. Empty = visible to all (including guests).
        match_prefix: If True, highlight when URL starts with route (useful for nested pages)
        badge: Optional badge text/count to display
        badge_color: Tailwind color class for badge (e.g., "bg-red-500")
        children: Nested menu items (max 2 levels supported)
        default_expanded: Whether submenu starts expanded (only for items with children)
    """

    key: str
    icon: str
    route: str | None = None
    roles: list[UserRole] = field(default_factory=list)
    match_prefix: bool = False
    badge: str | int | None = None
    badge_color: str = "bg-primary"
    children: list["MenuItem"] | None = None
    default_expanded: bool = False

    def has_children(self) -> bool:
        """Check if this item has nested children."""
        return bool(self.children)

    def is_active(self, current_path: str) -> bool:
        """Check if this menu item should be highlighted as active."""
        if self.route:
            if self.match_prefix:
                return current_path.startswith(self.route)
            return current_path == self.route
        # For parent items, check if any child is active
        if self.children:
            return any(child.is_active(current_path) for child in self.children)
        return False

    def is_visible_for_role(self, user_role: UserRole | None) -> bool:
        """Check if this item is visible for the given role."""
        # If no roles specified, visible to everyone (including guests)
        if not self.roles:
            return True
        # If user has no role (guest), not visible if roles are specified
        if user_role is None:
            return False
        # Check if user's role level meets the required level
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        for required_role in self.roles:
            required_level = ROLE_HIERARCHY.get(required_role, 0)
            if user_level >= required_level:
                return True
        return False


@dataclass
class MenuSection:
    """
    A section of menu items with an optional header.

    Attributes:
        key: Unique identifier for the section
        items: List of menu items in this section
        show_header: Whether to show the section header (with separator line)
        roles: Roles that can see this section header. Empty = visible to all.
    """

    key: str
    items: list[MenuItem]
    show_header: bool = True
    roles: list[UserRole] = field(default_factory=list)

    def is_visible_for_role(self, user_role: UserRole | None) -> bool:
        """Check if this section header is visible for the given role."""
        if not self.roles:
            return True
        if user_role is None:
            return False
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        for required_role in self.roles:
            if user_level >= ROLE_HIERARCHY.get(required_role, 0):
                return True
        return False

    def get_visible_items(self, user_role: UserRole | None) -> list[MenuItem]:
        """Get items visible to the given role."""
        visible = []
        for item in self.items:
            if item.is_visible_for_role(user_role):
                # For items with children, filter children too
                if item.children:
                    visible_children = [
                        c for c in item.children if c.is_visible_for_role(user_role)
                    ]
                    if visible_children:
                        # Create a copy with filtered children
                        filtered_item = MenuItem(
                            key=item.key,
                            icon=item.icon,
                            route=item.route,
                            roles=item.roles,
                            match_prefix=item.match_prefix,
                            badge=item.badge,
                            badge_color=item.badge_color,
                            children=visible_children,
                            default_expanded=item.default_expanded,
                        )
                        visible.append(filtered_item)
                else:
                    visible.append(item)
        return visible


# =============================================================================
# MENU LABELS - Translatable strings for menu items
# =============================================================================

def get_menu_label(key: str) -> str:
    """
    Get translated label for a menu item key.

    Add new keys here when adding menu items.
    """
    labels = {
        # Main section
        "dashboard": _("Dashboard"),
        # Admin section
        "admin": _("Admin"),
        "users": _("Users"),
        "contacts": _("Contacts"),
        "settings": _("Settings"),
        # Demo section
        "demo": _("Demo"),
        "books": _("Books"),
        "cars": _("Cars"),
        # Example nested items
        "analytics": _("Analytics"),
        "reports": _("Reports"),
    }
    return labels.get(key, key.replace("_", " ").title())


def get_section_label(key: str) -> str:
    """
    Get translated label for a section header.
    """
    labels = {
        "main": _("Main"),
        "admin": _("Admin"),
        "demo": _("Demo"),
        "settings": _("Settings"),
    }
    return labels.get(key, key.replace("_", " ").title())


# =============================================================================
# MENU CONFIGURATION - Edit this to change sidebar content
# =============================================================================

def get_menu_config() -> list[MenuSection]:
    """
    Define the sidebar menu structure.

    This is the SINGLE SOURCE OF TRUTH for sidebar content.
    Edit this function to add, remove, or reorganize menu items.

    Icon Reference (FontAwesome):
    - Use icon name without prefix: "fa-house" not "fa-solid fa-house"
    - The template switches between fa-regular (default) and fa-solid (hover/active)
    - Find icons at: https://fontawesome.com/search

    Role Reference:
    - UserRole.PENDING: Unverified users
    - UserRole.USER: Regular authenticated users
    - UserRole.MODERATOR: Moderators
    - UserRole.ADMIN: Administrators

    Examples:
        # Simple item visible to all:
        MenuItem(key="home", icon="fa-house", route="/")

        # Item only for admins:
        MenuItem(key="users", icon="fa-users", route="/admin/users",
                 roles=[UserRole.ADMIN])

        # Item with prefix matching (highlights for /books, /books/1, etc):
        MenuItem(key="books", icon="fa-book", route="/books", match_prefix=True)

        # Parent item with children (collapsible submenu):
        MenuItem(key="dashboards", icon="fa-gauge", route=None, children=[
            MenuItem(key="analytics", icon="fa-chart-line", route="/analytics"),
            MenuItem(key="reports", icon="fa-file-lines", route="/reports"),
        ])

        # Item with notification badge:
        MenuItem(key="inbox", icon="fa-inbox", route="/inbox",
                 badge=5, badge_color="bg-red-500")
    """
    return [
        # =====================================================================
        # MAIN SECTION - No header, always visible
        # =====================================================================
        MenuSection(
            key="main",
            show_header=False,
            items=[
                MenuItem(
                    key="dashboard",
                    icon="fa-chart-pie",
                    route="/",
                ),
            ],
        ),
        # =====================================================================
        # ADMIN SECTION - Only for admins
        # =====================================================================
        MenuSection(
            key="admin",
            show_header=True,
            roles=[UserRole.ADMIN],
            items=[
                MenuItem(
                    key="users",
                    icon="fa-users",
                    route="/admin/users",
                    match_prefix=True,
                    roles=[UserRole.ADMIN],
                ),
                MenuItem(
                    key="contacts",
                    icon="fa-address-book",
                    route="/admin/contacts",
                    match_prefix=True,
                    roles=[UserRole.ADMIN],
                ),
            ],
        ),
        # =====================================================================
        # DEMO SECTION - Visible to all
        # =====================================================================
        MenuSection(
            key="demo",
            show_header=True,
            items=[
                MenuItem(
                    key="books",
                    icon="fa-book",
                    route="/books",
                    match_prefix=True,
                ),
                MenuItem(
                    key="cars",
                    icon="fa-car",
                    route="/cars",
                    match_prefix=True,
                ),
            ],
        ),
    ]


# =============================================================================
# CONTEXT BUILDER - Used by templates
# =============================================================================

def get_user_role(user: "User | None") -> UserRole | None:
    """
    Determine the effective role of a user.

    Args:
        user: User object or None for guests

    Returns:
        UserRole enum value or None for guests
    """
    if user is None:
        return None

    # Check if user is active
    if not getattr(user, "is_active", False):
        return None

    # Use the role field from User model
    role = getattr(user, "role", None)
    if role and isinstance(role, UserRole):
        return role

    # Fallback: check is_superuser flag (maps to ADMIN)
    if getattr(user, "is_superuser", False):
        return UserRole.ADMIN

    return UserRole.USER


def build_sidebar_context(user: "User | None", current_path: str) -> dict:
    """
    Build the complete sidebar context for templates.

    Args:
        user: Current user object (or None for guests)
        current_path: Current URL path for highlighting active items

    Returns:
        Dictionary with sidebar data for template rendering:
        {
            "sections": [...],  # List of visible sections with items
            "user_role": "admin",  # Current user's role as string
        }
    """
    user_role = get_user_role(user)
    menu_config = get_menu_config()

    # Build visible sections
    visible_sections = []
    for section in menu_config:
        visible_items = section.get_visible_items(user_role)
        if not visible_items:
            continue

        # Build items data
        items_data = []
        for item in visible_items:
            item_data = {
                "key": item.key,
                "label": get_menu_label(item.key),
                "icon": item.icon,
                "route": item.route,
                "is_active": item.is_active(current_path),
                "badge": item.badge,
                "badge_color": item.badge_color,
                "has_children": item.has_children(),
                "default_expanded": item.default_expanded,
            }

            # Add children if present
            if item.children:
                item_data["children"] = [
                    {
                        "key": child.key,
                        "label": get_menu_label(child.key),
                        "icon": child.icon,
                        "route": child.route,
                        "is_active": child.is_active(current_path),
                        "badge": child.badge,
                        "badge_color": child.badge_color,
                    }
                    for child in item.children
                ]
                # Auto-expand if any child is active
                if any(child.is_active(current_path) for child in item.children):
                    item_data["default_expanded"] = True

            items_data.append(item_data)

        # Add section
        visible_sections.append(
            {
                "key": section.key,
                "label": get_section_label(section.key),
                "show_header": section.show_header
                and section.is_visible_for_role(user_role),
                "items": items_data,
            }
        )

    return {
        "sections": visible_sections,
        "user_role": user_role.value if user_role else "guest",
    }
