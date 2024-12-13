import asyncio
import aiomqtt
import ssl
import json
import logging as log

from options import options_change


class MqttClient:
    def __init__(self, options, queue_write, queue_read, devices):
        self.options = options
        self.queue_write = queue_write
        self.queue_read = queue_read
        self.devices = devices

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
                        if message.topic.matches(f"{self.stdown}/errors"):
                            self.on_errors(message)
                        if message.topic.matches(f"{self.stdown}/commands"):
                            await self.on_message_cmd(message)
                        if message.topic.matches(f"{self.stdown}/status_request"):
                            await self.on_message_stat(message)
                        if message.topic.matches(f"{self.stdown}/config_request"):
                            self.on_message_conf(message)
                        else:
                            self.on_message(message)
            except aiomqtt.MqttError:
                log.warning(f"Connection lost; Reconnecting in {interval} seconds ...")
                await asyncio.sleep(interval)

    def on_message(self, msg):
        log.debug("on_message %s %s %s", msg.topic, str(msg.qos), str(msg.payload))

    async def send_status(self, data):
        await self.client.publish(f"{self.sber_root_topic}/up/status", data)

    async def send_config(self, data):
        await self.client.publish(f"{self.sber_root_topic}/up/config", data)

    def on_errors(self, msg):
        log.info("Sber MQTT Errors: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

    async def on_message_cmd(self, msg):
        data = json.loads(msg.payload)
        # Command: {'devices': {'Relay_03': {'states': [{'key': 'on_off', 'value': {'type': 'BOOL'}}]}}}
        log.info("Sber MQTT Command: %s", data)
        for _id, v in data['devices'].items():
            for k in v['states']:
                type = k['value'].get('type', '')
                val = ''
                if type == 'BOOL':
                    val = k['value'].get('bool_value', False)
                if type == 'INTEGER':
                    val = k['value'].get('integer_value', 0)
                if type == 'ENUM':
                    val = k['value'].get('enum_value', '')
                self.devices.change_state(_id, k['key'], val)
            if self.devices.DB[_id].get('entity_ha', False):
                await self.send_data(_id)
            else:
                log.warning('Объект отсутствует в HA: ' + _id)
            await self.send_status(self.devices.do_mqtt_json_states_list([_id]))
        # log(DevicesDB.mqtt_json_states_list)

    async def on_message_stat(self, msg):
        data = json.loads(msg.payload).get('devices', [])
        log.info("GetStatus: " + str(msg.payload))
        await self.send_status(self.devices.do_mqtt_json_states_list(data))
        # log.debug("Answer: " + self.devices.mqtt_json_states_list)

    def on_message_conf(self, msg):
        log.info("Config: " + str(msg.topic) + " " + str(msg.qos) + " " + str(msg.payload))

    def on_global_conf(self, msg):
        data = json.loads(msg.payload)
        options_change(self.options, 'sd_http_api_endpoint', data.get('http_api_endpoint', ''))

    async def send_data(self, data):
        await self.queue_write.put(data)

    async def queue_processer(self):
        while True:
            if self.client is not None:
                break
            await asyncio.sleep(1)
        while True:
            data = await self.queue_read.get()
            match data["type"]:
                case "conf":
                    await self.send_config(data["data"])
                case "status":
                    await self.send_status(data["data"])
            self.queue_read.task_done()
