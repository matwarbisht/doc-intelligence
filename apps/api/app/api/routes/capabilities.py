from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_safeguard_service
from app.schemas.capabilities import CapabilitiesResponse
from app.services import SafeguardService

router = APIRouter()
Safeguards = Annotated[SafeguardService, Depends(get_safeguard_service)]


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities(service: Safeguards) -> CapabilitiesResponse:
    return CapabilitiesResponse.from_domain(service.capabilities)
