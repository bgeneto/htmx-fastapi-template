from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import settings
from .i18n import get_locale, get_translations
from .sidebar import build_sidebar_context

templates = Jinja2Templates(directory="templates")

# Configure Jinja2 with i18n extension
templates.env.add_extension("jinja2.ext.i18n")
templates.env.install_gettext_callables(  # type: ignore[attr-defined]
    gettext=lambda x: get_translations(get_locale()).gettext(x),
    ngettext=lambda s, p, n: get_translations(get_locale()).ngettext(s, p, n),
    newstyle=True,
)

# Add sidebar filter to templates
def sidebar_filter(request: Request) -> dict:
    """
    Template filter to build sidebar context.

    Called from templates as: {{ request | sidebar }}
    """
    user = getattr(request.state, "user", None)
    current_path = str(request.url.path)
    return build_sidebar_context(user, current_path)


templates.env.filters["sidebar"] = sidebar_filter

# Global template context for all templates
def get_template_context():
    """Get global context for all templates."""
    return {"enable_i18n": settings.ENABLE_I18N}


# Add global context function to templates
templates.env.globals.update(get_template_context())
