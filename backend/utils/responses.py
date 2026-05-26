from typing import Any, Optional
from backend.schemas.api_models import StandardResponse

def success_response(message: str, data: Optional[Any] = None) -> StandardResponse:
    """
    Helper function to generate a standardized success response.
    
    Args:
        message (str): A human-readable success message.
        data (Any, optional): The payload to include in the response. Defaults to empty dict.
        
    Returns:
        StandardResponse: The formatted response object.
    """
    return StandardResponse(
        status=200,
        message=message,
        data=data if data is not None else {}
    )
