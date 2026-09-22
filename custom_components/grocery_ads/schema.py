import dataclasses
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class AdItem:
    store: str
    item_name: str
    category: str
    price: float
    unit: str
    sale_type: str
    valid_from: date
    valid_to: date
    scraped_at: datetime
    # future hook: store_location_id: str | None = None

    def __post_init__(self):
        self.price = float(self.price)
        if isinstance(self.valid_from, str):
            self.valid_from = date.fromisoformat(self.valid_from)
        if isinstance(self.valid_to, str):
            self.valid_to = date.fromisoformat(self.valid_to)

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["valid_from"] = self.valid_from.isoformat()
        d["valid_to"] = self.valid_to.isoformat()
        d["scraped_at"] = self.scraped_at.isoformat()
        return d


@dataclass
class FlyerRef:
    """A pointer to a store's weekly ad flyer (PDF or image page(s)) that
    is displayed directly rather than parsed into individual items."""

    store: str
    urls: list[str]
    media_type: str  # "pdf" or "image"
    valid_from: date
    valid_to: date
    scraped_at: datetime

    def __post_init__(self):
        if isinstance(self.valid_from, str):
            self.valid_from = date.fromisoformat(self.valid_from)
        if isinstance(self.valid_to, str):
            self.valid_to = date.fromisoformat(self.valid_to)

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["valid_from"] = self.valid_from.isoformat()
        d["valid_to"] = self.valid_to.isoformat()
        d["scraped_at"] = self.scraped_at.isoformat()
        return d
