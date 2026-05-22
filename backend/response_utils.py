from fastapi import HTTPException


def success_response(message: str, data=None, status: str = "success") -> dict:
    return {
        "status": status,
        "message": message,
        "data": data,
    }


def api_error(status_code: int, message: str, data=None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "status": "error",
            "message": message,
            "data": data,
        },
    )
