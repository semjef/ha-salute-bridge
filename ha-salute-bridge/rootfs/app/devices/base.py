from pydantic import TypeAdapter

from const import VERSION
from utils import json_read, json_write

from .models import *

class Devices:
    devices: dict[str, DeviceModel]  # ключи в виде "category.entity_id"

    def __init__(self, categories, devices_file):
        self.devices = {}

        self.devices_file = devices_file
        self.categories = categories

        self.load()

    def load(self):
        data = json_read(self.devices_file)
        self.devices = {key: DeviceModel(**val) for key, val in data.items()}

    def save(self):
        ta = TypeAdapter(dict[str, DeviceModel])
        with open(self.devices_file, 'wb') as f:
            f.write(ta.dump_json(self.devices, indent=4))

    def update(self, key: str, data: DeviceModel):
        if key in self.devices:
            update_data = data.model_dump(exclude_unset=True)
            self.devices[key] = self.devices[key].model_copy(update=update_data)
        else:
            self.devices[key] = data

    def change_state(self, key, value):
        self.devices[key].state = value

    def __getitem__(self, key):
        if key not in self.devices:
            return None
        return self.devices[key].model_copy()  # Возвращаем для предотвращения изменений

    def __iter__(self):
        for key, val in self.devices.items():
            yield key, val.model_copy()
