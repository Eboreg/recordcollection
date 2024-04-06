from abc import ABC
from dataclasses import dataclass, fields
from typing import Any


@dataclass
class AbstractBaseRecord(ABC):
    @classmethod
    def from_dict(cls, d: dict):
        try:
            field_names = [f.name for f in fields(cls)]
            return cls(
                **{
                    cls.key_to_attr(k): cls.serialize_field(k, v)
                    for k, v in d.items()
                    if cls.key_to_attr(k) in field_names
                }
            )
        except Exception as e:
            print(d)
            raise e

    @classmethod
    def key_to_attr(cls, key: str) -> str:
        """JSON key to class attribute name"""
        return key.replace("-", "_")

    @classmethod
    # pylint: disable=unused-argument
    def serialize_field(cls, key: str, value: Any):
        return value

    def to_dict(self) -> dict[str, Any]:
        field_names = [f.name for f in fields(self)]
        return {f: getattr(self, f) for f in field_names}
