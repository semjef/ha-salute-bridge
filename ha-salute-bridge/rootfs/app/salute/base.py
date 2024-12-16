import asyncio
import logging

import aiomqtt
import ssl
import json
import logging as log

from devices import Devices, DeviceModel, DeviceModelsEnum, LightAttrsEnum
from options import options_change


class SaluteClient:
    def __init__(self, options, queue_write, queue_read, devices: Devices, categories):
        self.options = options
        self.queue_write = queue_write
        self.queue_read = queue_read
        self.devices = devices
        self.categories = categories

        self.client = None
        self.sber_root_topic = f"sberdevices/v1/{options['sd_mqtt_login']}"
        self.stdown = f"{self.sber_root_topic}/down"

    async def listen(self):
        client = aiomqtt.Client(
            hostname=self.options['sd_mqtt_broker'],
            port=self.options['sd_mqtt_broker_port'],
            username=self.options['sd_mqtt_login'],
            password=self.options['sd_mqtt_password'],
            tls_params=aiomqtt.TLSParameters(
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_NONE,
                tls_version=None
            ),
            tls_insecure=True
        )
        interval = 5  # Seconds
        while True:
            try:
                async with client:
                    self.client = client
                    await client.subscribe(f"{self.stdown}/#")
                    await client.subscribe("sberdevices/v1/__config")
                    async for message in client.messages:
                        if message.topic.matches(f"sberdevices/v1/__config"):
                            self.on_global_conf(message)
                        elif message.topic.matches(f"{self.stdown}/errors"):
                            self.on_errors(message)
                        elif message.topic.matches(f"{self.stdown}/commands"):
                            await self.on_message_cmd(message)
                        elif message.topic.matches(f"{self.stdown}/status_request"):
                            await self.on_message_stat(message)
                        elif message.topic.matches(f"{self.stdown}/config_request"):
                            self.on_message_conf(message)
                        else:
                            self.on_message(message)
            except aiomqtt.MqttError:
                log.warning(f"Connection lost; Reconnecting in {interval} seconds ...")
                await asyncio.sleep(interval)

    def on_message(self, msg):
        log.debug("on_message %s %s %s", msg.topic, msg.qos, msg.payload)

    async def send_status(self, data):
        logging.debug("send_status:%s", data)
        await self.client.publish(f"{self.sber_root_topic}/up/status", data)

    async def send_config(self, data):
        logging.debug("send_config:%s", data)
        await self.client.publish(f"{self.sber_root_topic}/up/config", data)

    def on_errors(self, msg):
        log.info("Sber MQTT Errors: %s %s %s", msg.topic, msg.qos, msg.payload)

    async def on_message_cmd(self, msg):
        data = json.loads(msg.payload)
        # Command: {'devices': {'Relay_03': {'states': [{'key': 'on_off', 'value': {'type': 'BOOL'}}]}}}
        log.info("Sber MQTT Command: %s", data)
        for entity_id, v in data['devices'].items():
            device = self.devices[entity_id]
            for state in v['states']:
                val_type = state['value'].get('type', '')
                val = ''
                match val_type:
                    case 'BOOL':
                        val = state['value'].get('bool_value', False)
                    case 'INTEGER':
                        val = int(state['value'].get('integer_value', 0))
                    case 'ENUM':
                        val = state['value'].get('enum_value', '')
                match state['key']:
                    case 'on_off':
                        device.state = "on" if val else "off"
                    case 'light_brightness':
                        val = int(val / 10 * 2.55)  # приводим из 50-1000 к диапозону 1-255
                        device.attributes[LightAttrsEnum.brightness] = val
            self.devices.update(entity_id, device)
            await self.send_data(entity_id)
            # await self.send_status(self.devices.do_mqtt_json_states_list([_id]))
        # log(DevicesDB.mqtt_json_states_list)

    async def on_message_stat(self, msg):
        data = json.loads(msg.payload).get('devices', [])
        log.info("GetStatus: %s", msg.payload)
        await self.send_status(self.get_salute_states_list(data))
        # log.debug("Answer: " + self.devices.mqtt_json_states_list)

    def on_message_conf(self, msg):
        log.info("Config: %s %s %s", msg.topic, msg.qos, msg.payload)

    def on_global_conf(self, msg):
        data = json.loads(msg.payload)
        options_change(self.options, 'sd_http_api_endpoint', data.get('http_api_endpoint', ''))

    async def send_data(self, data):
        await self.queue_write.put(data)

    def get_salute_devices_list(self):
        manufacturer = 'HA SaluteBridge'
        devices = [{
            "id": "root",
            "name": "HA Bridge hub",
            'model': {
                'id': 'ID_root_hub',
                'manufacturer': manufacturer,
                'model': 'SBHub',
                'description': "HA SaluteBridge HUB",
                'category': 'hub',
                'features': ['online']
            }
        }]
        for entity_id, device in self.devices:
            if not device.enabled:
                continue
            data = {
                'id': entity_id,
                'name': device.name,
                'model_id': ''
            }
            category_name = self.get_salute_category_name(device)
            category = self.categories.get(category_name)
            features = []
            for ft in category:
                if ft.get('required', False):
                    features.append(ft['name'])
                if (
                    ft['name'] == 'light_brightness' and
                    device.features and
                    LightAttrsEnum.brightness in device.features
                ):
                    features.append(ft['name'])
                # Будем выдавать список из доступных фич для каждого типа в вебе и
                # юзер сам будет включать их для каждого элемента
            data['model'] = {
                'id': f'ID_{entity_id}',
                'manufacturer': manufacturer,
                'model': 'Model_' + device.model,
                'category': category_name,
                'features': features
            }
            devices.append(data)
        return json.dumps({'devices': devices}, ensure_ascii=False, sort_keys=True)

    def get_salute_states_list(self, entitys: list | None = None):
        devices = {}
        if not entitys:
            entitys = self.devices.keys()
        for entity_id in entitys:
            device = self.devices[entity_id]
            if device is None or not device.enabled:
                continue
            features = self.get_features(device)
            devices[entity_id] = {'states': features}
        return json.dumps({'devices': devices}, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def get_salute_category_name(device):
        ha_to_salude_category = {
            "light": "light",
            "switch": "relay",
            "script": "relay",
            "sensor": "sensor_temp"
        }
        # Ещё нужно учесть device.model
        return ha_to_salude_category.get(device.category, "relay")

    def get_features(self, device):
        category_name = self.get_salute_category_name(device)
        category = self.categories.get(category_name)
        features = []
        match device.category:
            case 'light':
                features.append(self.get_state_value("online", "BOOL", device.state != "unavailable"))
                features.append(self.get_state_value("on_off", "BOOL", device.state == "on"))
                if device.features:
                    if LightAttrsEnum.brightness in device.features:
                        val = device.attributes.get(LightAttrsEnum.brightness)
                        if val is not None:  # Включено, но нету - не передаём
                            val = int(val / 2.55 * 10)  # приводим из 1-255 к диапозону 50-1000
                            if val < 50:
                                val = 50
                            if val > 1000:
                                val = 1000
                            features.append(self.get_state_value("light_brightness", "INTEGER", val))
            case _:
                # Не обрабатываем ничего, кроме этих типов
                pass
        return features

    @staticmethod
    def get_state_value(name, data_type, value):
        # {'key':'online','value':{"type": "BOOL", "bool_value": True}}
        r = {}
        if name == 'temperature':
            value = value * 10
        if data_type == 'BOOL':
            r = {'key': name, 'value': {'type': 'BOOL', 'bool_value': bool(value)}}
        if data_type == 'INTEGER':
            r = {'key': name, 'value': {'type': 'INTEGER', 'integer_value': int(value)}}
        if data_type == 'ENUM':
            r = {'key': name, 'value': {'type': 'ENUM', 'enum_value': value}}
        return r


    async def queue_processer(self):
        while True:
            if self.client is not None:
                break
            await asyncio.sleep(1)
        while True:
            data = await self.queue_read.get()
            match data["type"]:
                case "conf":
                    await self.send_config(self.get_salute_devices_list())
                case "status":
                    entity_id = data["data"]
                    await self.send_status(self.get_salute_states_list([entity_id]))
            self.queue_read.task_done()
