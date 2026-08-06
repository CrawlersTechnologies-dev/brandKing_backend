from rest_framework.views import exception_handler
from common.responses import error_response

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return error_response(
            message="Validation error" if response.status_code == 400 else "An error occurred",
            errors=response.data,
            status=response.status_code
        )
    return response
