from pydantic import BaseModel

class SquareMeterPriceRequest(BaseModel):
    url: str
    dikte: float
    lengte: float
    breedte: float
    country: str = 'nl'
    quantity: int = 1  # Standaardwaarde is 1 stuk

class ShippingRequest(BaseModel):
    url: str
    country: str = 'nl'
    package_type: int = 1  # 1-6 for different package sizes
    thickness: float = None  # Optional override for package thickness
    quantity: int = None  # Optional override for package quantity
