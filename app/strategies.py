from typing import Protocol

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from .i18n import gettext as _


class ValidationStrategy(Protocol):
    def translate(self, err: ErrorDetails, field: str) -> str: ...


class MinLengthName(ValidationStrategy):
    def translate(self, err: ErrorDetails, field: str) -> str:
        return _("Name must be at least 2 characters")


class MinLengthMessage(ValidationStrategy):
    def translate(self, err: ErrorDetails, field: str) -> str:
        return _("Message must be at least 5 characters")


class InvalidEmail(ValidationStrategy):
    def translate(self, err: ErrorDetails, field: str) -> str:
        return _("Please enter a valid email address")


class RequiredField(ValidationStrategy):
    def translate(self, err: ErrorDetails, field: str) -> str:
        return _("This field is required")


class DefaultStrategy(ValidationStrategy):
    def translate(self, err: ErrorDetails, field: str) -> str:
        return err["msg"]


# Registry: (msg_snippet, field) -> strategy
VALIDATION_REGISTRY = {
    ("String should have at least", "name"): MinLengthName(),
    ("String should have at least", "message"): MinLengthMessage(),
    ("value is not a valid email address", "email"): InvalidEmail(),
    ("Field required", "name"): RequiredField(),
    ("Field required", "email"): RequiredField(),
    ("Field required", "message"): RequiredField(),
    ("Field required", "full_name"): RequiredField(),
}


def handle_validation_error(e: ValidationError) -> dict[str, str]:
    """Translate Pydantic errors using Strategy."""
    errors = {}
    for err in e.errors():
        loc = err["loc"]
        field = str(loc[-1])
        msg = err["msg"]
        # Find matching (snippet, field) key
        matching_key = next(
            (
                (k[0], k[1])
                for k in VALIDATION_REGISTRY.keys()
                if k[0] in msg and k[1] == field
            ),
            ("default", field),
        )
        strategy = VALIDATION_REGISTRY.get(matching_key, DefaultStrategy())
        errors[field] = strategy.translate(err, field)
    return errors


from abc import ABC, abstractmethod

from .models import User, UserRole
from .repository import verify_password


class AuthVerifier(ABC):
    @abstractmethod
    def verify(self, **kwargs) -> bool:
        pass


class AdminLoginVerifier(AuthVerifier):
    def __init__(self, user: User):
        self.user = user

    def verify(self, password: str) -> bool:
        return (
            self.user is not None
            and self.user.hashed_password is not None
            and self.user.role == UserRole.ADMIN
            and verify_password(password, self.user.hashed_password)
            and self.user.is_active
        )


def create_admin_login_verifier(user: User) -> AuthVerifier:
    return AdminLoginVerifier(user)
