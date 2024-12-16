from pydantic import TypeAdapter

from const import VERSION
from utils import json_read, json_write

from .models import *

class Devices:
    _devices: dict[str, DeviceModel]  # ключи в виде "category.entity_id"

    def __init__(self, devices_file):
        self._devices = {}

        self.devices_file = devices_file

        self.load()

    def load(self):
        data = json_read(self.devices_file)
        self._devices = {key: DeviceModel(**val) for key, val in data.items()}

    def save(self):
        with open(self.devices_file, 'wb') as f:
            f.write(self.as_json(indent=4))

    def as_json(self, **kwargs):
        ta = TypeAdapter(dict[str, DeviceModel])
        return ta.dump_json(self._devices, **kwargs)

    def as_dict(self, **kwargs):
        ta = TypeAdapter(dict[str, DeviceModel])
        return ta.dump_python(self._devices, **kwargs)

    def update(self, key: str, data: DeviceModel | dict):
        if key in self._devices:
            if isinstance(data, DeviceModel):
                data = data.model_dump(exclude_unset=True)
            self._devices[key] = self._devices[key].model_copy(update=data)
        else:
            data.model = DeviceModelsEnum.light
            self._devices[key] = data

    def change_state(self, key, value):
        self._devices[key].state = value

    def __getitem__(self, key):
        if key not in self._devices:
            return None
        return self._devices[key].model_copy()  # Возвращаем для предотвращения изменений

    def __iter__(self):
        for key, val in self._devices.items():
            yield key, val.model_copy()

    def keys(self):
        return self._devices.keys()
