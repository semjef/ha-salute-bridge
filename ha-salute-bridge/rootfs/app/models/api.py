from pydantic import BaseModel, Field

from devices.models import LightAttrsEnum


class DevicesEditModel(BaseModel):
    devices: list | None = None


class FeatureEditModel(BaseModel):
    entity_id: str
    feature: LightAttrsEnum
    state: bool