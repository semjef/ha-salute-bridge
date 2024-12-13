"""
За основу берём названия в HA
В сберовкие данные переводим в конвертере
"""

from pydantic import BaseModel, Field


class LightModel(BaseModel):
    is_on: bool = False # on_off
    brightness: int | None = Field(gt=0, le=255) # light_brightness INTEGER(50,1000)
    # light_colour_temp
    # light_scene
    # light_mode
    # light_colour "colour_value": { "h": 360, "s": 1000, "v": 1000 }


class LedStripModel(BaseModel):
    is_on: bool = False # on_off
    brightness: int | None = Field(gt=0, le=255) # light_brightness INTEGER(50,1000)
    # light_colour_temp
    # light_mode
    # light_colour "colour_value": { "h": 360, "s": 1000, "v": 1000 }


class DeviceModel(BaseModel):
    enabled: bool = False
    properties: LightModel = Field(title="Наследуемая модель")


class DevisesListModel(BaseModel):
    devices: list[DeviceModel]
