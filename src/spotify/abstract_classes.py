from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from recordcollection.abstract_classes import AbstractBaseRecord


ABR = TypeVar("ABR", bound=AbstractBaseRecord)


@dataclass
class AbstractSpotifyResponse(AbstractBaseRecord, ABC, Generic[ABR]):
    items: list[ABR]
    limit: int
    offset: int
    total: int
    next: str | None = None
    previous: str | None = None

    @classmethod
    @abstractmethod
    def serialize_item(cls, value: Any) -> ABR:
        ...

    @classmethod
    def serialize_field(cls, key: str, value: Any):
        if key == "items":
            return [cls.serialize_item(d) for d in value]
        return super().serialize_field(key, value)
