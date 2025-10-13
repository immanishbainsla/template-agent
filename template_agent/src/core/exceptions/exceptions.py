from __future__ import annotations

from enum import Enum

from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR, \
    HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN


class AppExceptionCode(Enum):
    """Defines custom App Exception codes for this service, associated with HTTP Status codes."""
    BAD_REQUEST_ERROR = (HTTP_400_BAD_REQUEST, "Bad Request", "E_001")
    NOT_FOUND_ERROR = (HTTP_404_NOT_FOUND, "Not Found", "E_002")
    INTERNAL_SERVER_ERROR = (HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error", "E_003")
    UNAUTHORISED_ACCESS_ERROR = (HTTP_401_UNAUTHORIZED, "Unauthorized", "E_004")
    FORBIDDEN_ACCESS_ERROR = (HTTP_403_FORBIDDEN, "Forbidden", "E_005")
    TOOL_CALL_ERROR = (HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error", "E_006")
    PRODUCTION_MCP_CONNECTION_ERROR = (HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error", "E_007")
    CONFIGURATION_INITIALIZATION_ERROR = (HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error", "E_008")
    CONFIGURATION_VALIDATION_ERROR = (HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error", "E_009")

    def __init__(self, response_code:str, message:str, error_code:str):
        self._response_code = response_code
        self._message = message
        self._error_code = error_code

    @property
    def response_code(self):
        return self._response_code

    @property
    def message(self):
        return self._message

    @property
    def error_code(self):
        return self._error_code

    def __str__(self):
        return f"response_code={self.response_code}, message={self.message}, error_code={self.error_code}"



class AppException(Exception):
    """Base exception for application"""
    def __init__(self, detail_message:str, app_exception_code:AppExceptionCode = AppExceptionCode.INTERNAL_SERVER_ERROR):
        self._detail_message = detail_message
        self._app_exception_code = app_exception_code
        super().__init__(detail_message)

    @property
    def detail_message(self):
        return self._detail_message

    @property
    def response_code(self):
        return self._app_exception_code.response_code

    @property
    def message(self):
        return self._app_exception_code.message

    @property
    def error_code(self):
        return self._app_exception_code.error_code

    def __str__(self):
        return f"response_code={self.response_code}, message={self.message}, detail_message={self.detail_message}, error_code={self.error_code}"



class ToolCallException(AppException):
    """Raised when Tool call fails"""
    def __init__(self, detail_message:str):
        super().__init__(detail_message, AppExceptionCode.TOOL_CALL_ERROR)

    def __str__(self):
        return super().__str__()

class UnauthorizedException(AppException):
    """Raised when user Authentication fails"""
    def __init__(self, detail_message:str):
        super().__init__(detail_message, AppExceptionCode.UNAUTHORISED_ACCESS_ERROR)

    def __str__(self):
        return super().__str__()

class ForbiddenException(AppException):
    """Raised when user is forbidden"""
    def __init__(self, detail_message:str):
        super().__init__(detail_message, AppExceptionCode.FORBIDDEN_ACCESS_ERROR)

    def __str__(self):
        return super().__str__()