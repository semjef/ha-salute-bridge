from pydantic import BaseModel, Field


class DevicesEditModel(BaseModel):
    devices: list | None = None