class DomainError(Exception):
    code: str | None = None


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class InvalidRequestError(DomainError):
    pass
