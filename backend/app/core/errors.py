from typing import Any


class AppError(Exception):
    """Base for every error the API returns. Never leaks provider internals."""

    code = "INTERNAL_ERROR"
    status_code = 500
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None, **details: Any) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ConfigError(AppError):
    code = "CONFIG_ERROR"
    status_code = 500
    message = "The server is misconfigured."


class InvalidAudioError(AppError):
    code = "INVALID_AUDIO"
    status_code = 400
    message = "The uploaded audio could not be read."


class UnsupportedAudioFormatError(AppError):
    code = "UNSUPPORTED_AUDIO_FORMAT"
    status_code = 415
    message = "That audio format is not supported."


class AudioTooLargeError(AppError):
    code = "AUDIO_TOO_LARGE"
    status_code = 413
    message = "The uploaded audio is too large."


class SessionNotFoundError(AppError):
    code = "SESSION_NOT_FOUND"
    status_code = 404
    message = "No such conversation session."


class TurnNotFoundError(AppError):
    code = "TURN_NOT_FOUND"
    status_code = 404
    message = "No such conversation turn."


class SessionNotActiveError(AppError):
    code = "SESSION_NOT_ACTIVE"
    status_code = 409
    message = "This conversation has already ended."


class SessionExpiredError(AppError):
    code = "SESSION_EXPIRED"
    status_code = 410
    message = "This conversation expired after a period of inactivity."


class AnalysisNotFoundError(AppError):
    code = "ANALYSIS_NOT_FOUND"
    status_code = 404
    message = "This conversation has not been analysed yet."


class FeatureDisabledError(AppError):
    code = "FEATURE_DISABLED"
    status_code = 501
    message = "This feature is not enabled on this server."


class ProviderUnavailableError(AppError):
    code = "PROVIDER_UNAVAILABLE"
    status_code = 502
    message = "The AI provider is currently unavailable."


class ProviderTimeoutError(AppError):
    code = "PROVIDER_TIMEOUT"
    status_code = 504
    message = "The AI provider took too long to respond."


class ProviderBadResponseError(AppError):
    code = "PROVIDER_BAD_RESPONSE"
    status_code = 502
    message = "The AI provider returned a response we could not understand."


class StorageError(AppError):
    code = "STORAGE_ERROR"
    status_code = 500
    message = "Audio could not be stored or retrieved."
