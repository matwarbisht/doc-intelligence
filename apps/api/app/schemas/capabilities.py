from pydantic import BaseModel

from app.services import Capabilities


class CapabilitiesResponse(BaseModel):
    public_signup: bool
    uploads: bool
    processing: bool
    processing_retries: bool
    ask: bool

    @classmethod
    def from_domain(cls, capabilities: Capabilities) -> "CapabilitiesResponse":
        return cls(
            public_signup=capabilities.public_signup,
            uploads=capabilities.uploads,
            processing=capabilities.processing,
            processing_retries=capabilities.processing_retries,
            ask=capabilities.ask,
        )
