"""
За основу берём названия в HA
В сберовкие данные переводим в конвертере
"""
from enum import StrEnum, auto

from pydantic import BaseModel, Field


class DeviceModelsEnum(StrEnum):
    light = auto()
    led_strip = auto()
    relay = auto()
    scenario_button = auto()
    sensor_temp = auto()
    hvac_radiator = auto()


class LightAttrsEnum(StrEnum):
    brightness = auto()


class ButtonAttrsEnum(StrEnum):
    button_event = auto()


class SensorAttrsEnum(StrEnum):
    temperature = auto()


class HvacRadiatorAttrsEnum(StrEnum):
    temperature = auto()
    hvac_temp_set = auto()


class DeviceModel(BaseModel):
    entity_id: str = Field(title="Идентификатор устройства из HA")
    category: str = Field(title="Тип устройства из HA")
    enabled: bool | None = None
    name: str | None = None
    state: str
    model: DeviceModelsEnum | None = Field(title="Идентификатор в Salute", default=None)
    attributes: dict | None = None
    features: list[LightAttrsEnum | ButtonAttrsEnum] | None = None
