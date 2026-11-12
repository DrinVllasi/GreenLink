from pydantic import BaseModel, Field


class QuoteIn(BaseModel):
    route_id: int
    weight_kg: float = Field(gt=0, le=10)
    sender_id: int | None = None  # optional: lets the quote show the credit discount


class ParcelIn(BaseModel):
    sender_id: int
    route_id: int
    receiver_name: str = Field(min_length=2, max_length=120)
    receiver_phone: str = Field(min_length=6, max_length=32)
    weight_kg: float = Field(gt=0, le=10)
    content_type: str
    use_credits: bool = False

class ScanIn(BaseModel):
    actor_id: int | None = None  # who scanned (agent / driver); optional in the demo


class CollectIn(BaseModel):
    pickup_code: str
