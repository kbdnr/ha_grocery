from abc import ABC, abstractmethod
from ..schema import AdItem, FlyerRef

# Several store sites sit behind Cloudflare and block requests' bare
# "Mozilla/5.0" User-Agent; a fuller browser-like header set gets through.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _enforce_store_id(cls) -> None:
    # Determine if cls is concrete by checking whether any abstract methods
    # from parent classes remain unimplemented in cls.__dict__.
    # (cls.__abstractmethods__ is not yet set when __init_subclass__ fires,
    # so we inspect __isabstractmethod__ on inherited members directly.)
    remaining_abstract = {
        name
        for base in cls.__mro__[1:]
        for name, val in base.__dict__.items()
        if getattr(val, '__isabstractmethod__', False) and name not in cls.__dict__
    }
    if not remaining_abstract:
        # Only enforce store_id on concrete subclasses
        if not isinstance(getattr(cls, 'store_id', None), str):
            raise TypeError(f"{cls.__name__} must define store_id as a str class attribute")


class BaseConnector(ABC):
    store_id: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _enforce_store_id(cls)

    @abstractmethod
    def fetch(self) -> list[AdItem]: ...


class FlyerConnector(ABC):
    """A connector for stores whose weekly ad is a flyer (PDF or image)
    that gets displayed directly rather than parsed into AdItems."""

    store_id: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _enforce_store_id(cls)

    @abstractmethod
    def fetch(self) -> FlyerRef | None: ...
