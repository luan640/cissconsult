from contextvars import ContextVar


_current_company_id: ContextVar[int | None] = ContextVar(
    'current_company_id',
    default=None,
)


def set_current_company_id(company_id: int | None):
    return _current_company_id.set(company_id)


def reset_current_company_id(token) -> None:
    _current_company_id.reset(token)


def get_current_company_id() -> int | None:
    return _current_company_id.get()
