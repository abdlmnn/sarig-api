from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


DEFAULT_SUNSET = "2026-12-31"


class DeprecationHeaderMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        try:
            path = request.path or ""
            if path.startswith("/api/v1/"):
                response["Deprecation"] = "true"
                response["Sunset"] = getattr(settings, "API_V1_SUNSET", DEFAULT_SUNSET)
                response["Link"] = (
                    '<https://docs.kauyagan.local/migration/v1-to-v2>; '
                    'rel="describedby"'
                )
        except Exception:
            pass
        return response
