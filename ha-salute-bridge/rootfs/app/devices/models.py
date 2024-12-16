"""
За основу берём названия в HA
В сберовкие данные переводим в конвертере
"""
from enum import StrEnum, auto

from pydantic import BaseModel, Field


class DeviceModelsEnum(StrEnum):
    light = auto()
    led_strip = auto()


class LightAttrsEnum(StrEnum):
    brightness = auto()


class DeviceModel(BaseModel):
    entity_id: str = Field(title="Идентификатор устройства из HA")
    category: str = Field(title="Тип устройства из HA")
    enabled: bool | None = None
    name: str | None = None
    state: str
    model: DeviceModelsEnum | None = None
    features: list[LightAttrsEnum] | None = None
    attributes: dict | None = None
