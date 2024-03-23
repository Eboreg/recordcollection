from abc import ABC
from dataclasses import dataclass, fields
from typing import Any


@dataclass
class AbstractBaseRecord(ABC):
    @classmethod
    def from_dict(cls, d: dict):
        try:
            field_names = [f.name for f in fields(cls)]
            return cls(**{k: cls.serialize_field(k, v) for k, v in d.items() if k in field_names})
        except Exception as e:
            print(d)
            raise e

    @classmethod
    # pylint: disable=unused-argument
    def serialize_field(cls, key: str, value: Any):
        return value
