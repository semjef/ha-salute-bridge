import json
import os

import requests
import logging as log

from const import CATEGORIES_FILENAME, DEVICES_FILENAME
from utils import json_read, json_write

VERSION = '1.0.15'


def GetCategory(options):
    hds = {'content-type': 'application/json'}
    auth = (options['sd_mqtt_login'], options['sd_mqtt_password'])
    categories_url = f"{options['sd_http_api_endpoint']}/v1/mqtt-gate/categories"
    if not os.path.exists(CATEGORIES_FILENAME):
        log.info('Файл категорий отсутствует. Получаем...')
        categories = {}
        SD_Categories = requests.get(
            categories_url,
            headers=hds,
            auth=auth
        ).json()
        for id in SD_Categories['categories']:
            log.debug('Получаем опции для котегории: %s', id)
            SD_Features = requests.get(
                f"{categories_url}/{id}/features",
                headers=hds,
                auth=auth
            ).json()
            categories[id] = SD_Features['features']
        #   log(Categories)
        json_write('categories.json', categories)
    else:
        log.info('Список категорий получен из файла: ' + CATEGORIES_FILENAME)
        categories = json_read(CATEGORIES_FILENAME)
    return categories


class DevicesDB:
    def __init__(self, categories):
        self.fDB = DEVICES_FILENAME
        if not os.path.exists(self.fDB):
            json_write(self.fDB, {})
        self.DB = json_read(self.fDB)
        self.categories = categories
        for id in self.DB:
            if self.DB[id].get('enabled', None) is None:
                self.DB[id]['enabled'] = False

        self.mqtt_json_devices_list = '{}'
        self.mqtt_json_states_list = '{}'
        self.http_json_devices_list = '{}'
        #      self.do_mqtt_json_devices_list()
        #      self.do_mqtt_json_states_list({})
        self.do_http_json_devices_list()

    def NewID(self, a):
        r = ''
        for i in range(1, 99):
            r = a + '_' + ('00' + str(i))[-2:]
            if self.DB.get(r, None) is None:
                return r

    def save_DB(self):
        json_write(self.fDB, self.DB)

    #      self.do_http_json_devices_list()

    def clear(self, d):
        self.DB = {}
        self.save_DB()

    def dev_add(self):
        print('device_Add')

    def dev_del(self, id):
        self.DB.pop(id, None)
        self.save_DB()
        log.debug('Delete Device: ' + id + '!')

    def dev_inBase(self, id):
        if self.DB.get(id, None) is None:
            return False
        else:
            return True

    def change_state(self, id, key, value):
        if self.DB.get(id, None) is None:
            log.debug('Device id=%s not found', id)
            return
        if self.DB[id].get('States', None) is None:
            log.debug('Device id=%s States not Found. Create.', id)
            self.DB[id]['States'] = {}
        if self.DB[id]['States'].get(key, None) is None:
            log.debug('Device id=%s key=%s not Found. Create.', id, key)
        self.DB[id]['States'][key] = value

    #      self.do_mqtt_json_states_list([id])

    def get_states(self, id):
        d = self.DB.get(id, {})
        return d.get('States', {})

    def get_state(self, id, key):
        d = self.DB.get(id, {})
        s = d.get('States', {})
        k = s.get(key, None)
        if k:
            return k

    def update_only(self, id, d):
        if self.DB.get(id, None) is not None:
            for k, v in d.items():
                self.DB[id][k] = d.get(k, v)
            self.save_DB()

    def update(self, id, d, save=False):
        fl = {'enabled': False, 'name': '', 'default_name': '', 'nicknames': [], 'home': '', 'room': '', 'groups': [],
              'model_id': '', 'category': '', 'hw_version': VERSION, 'sw_version': VERSION, 'entity_ha': False,
              'entity_type': '', 'friendly_name': ''}
        if self.DB.get(id, None) is None:
            log.debug('Device %s Not Found. Adding', id)
            self.DB[id] = {}
            for k, v in fl.items():
                self.DB[id][k] = d.get(k, v)
            if d['category'] == 'scenario_button':
                self.DB[id]['States'] = {'button_event': ''}

        for k, v in d.items():
            self.DB[id][k] = d.get(k, v)
        if self.DB[id]['name'] == '':
            self.DB[id]['name'] = self.DB[id]['friendly_name']
        if save:
            self.save_DB()

    def DeviceStates_mqttSber(self, id):
        d = self.DB.get(id, None)
        #      log(d)
        r = []
        if d is None:
            log.warning('Запрошен несуществующий объект: %s', id)
            return r
        s = d.get('States', None)
        if s is None:
            log.warning('У объекта: %s отсутствует информация о состояниях', id)
            return r
        if d['category'] == 'relay':
            v = s.get('on_off', False)
            r.append({'key': 'online', 'value': {"type": "BOOL", "bool_value": True}})
            r.append({'key': 'on_off', 'value': {"type": "BOOL", "bool_value": v}})
        if d['category'] == 'sensor_temp':
            v = round(s.get('temperature', 0) * 10)
            r.append({'key': 'online', 'value': {"type": "BOOL", "bool_value": True}})
            r.append({'key': 'temperature', 'value': {"type": "INTEGER", "integer_value": v}})

        if d['category'] == 'scenario_button':
            v = s.get('button_event', 'click')
            r.append({'key': 'online', 'value': {"type": "BOOL", "bool_value": True}})
            r.append({'key': 'button_event', 'value': {"type": "ENUM", "enum_value": v}})

        if d['category'] == 'hvac_radiator':
            #         log('hvac')
            v = round(s.get('temperature', 0) * 10)
            r.append({'key': 'online', 'value': {"type": "BOOL", "bool_value": True}})
            r.append({'key': 'on_off', 'value': {"type": "BOOL", "bool_value": True}})
            r.append({'key': 'temperature', 'value': {"type": "INTEGER", "integer_value": v}})
            r.append({'key': 'hvac_temp_set', 'value': {"type": "INTEGER", "integer_value": 30}})
        #         log(r)

        #      for k,v in s.items():
        #         log(k)
        #         if (isinstance(v,bool)):
        #            o={'key':k,'value':{"type": "BOOL", "bool_value": v}}
        #         elif (isinstance(v, int)):
        #            o={'key':k,'value':{"type": "INTEGER", "integer_value": v}}
        #         else:
        #            log(v)
        #            o={'key':k,'value':{"type": "BOOL", "bool_value": False}}
        #         r.append(o)
        return r

    def do_mqtt_json_devices_list(self):
        Dev = {}
        Dev['devices'] = []
        Dev['devices'].append({"id": "root", "name": "Вумный контроллер", 'hw_version': VERSION, 'sw_version': VERSION})
        Dev['devices'][0]['model'] = {'id': 'ID_root_hub', 'manufacturer': 'Janch', 'model': 'VHub',
                                      'description': "HA MQTT SberGate HUB", 'category': 'hub', 'features': ['online']}
        for k, v in self.DB.items():
            if v.get('enabled', False):
                d = {'id': k, 'name': v.get('name', ''), 'default_name': v.get('default_name', '')}
                d['home'] = v.get('home', 'Мой дом')
                d['room'] = v.get('room', '')
                #            d['groups']=['Спальня']
                d['hw_version'] = VERSION
                d['sw_version'] = VERSION
                dev_cat = v.get('category', 'relay')
                c = self.categories.get(dev_cat)
                f = []
                for ft in c:
                    if ft.get('required', False):
                        f.append(ft['name'])
                    else:
                        for st in self.get_states(k):
                            if ft['name'] == st:
                                f.append(ft['name'])

                d['model'] = {'id': 'ID_' + dev_cat, 'manufacturer': 'Janch', 'model': 'Model_' + dev_cat,
                              'category': dev_cat, 'features': f}
                #            log(d['model'])
                d['model_id'] = ''
                Dev['devices'].append(d)
        self.mqtt_json_devices_list = json.dumps(Dev)
        log.debug('New Devices List for MQTT: %s', str(self.mqtt_json_devices_list))
        return self.mqtt_json_devices_list

    def DefaultValue(self, feature):
        t = feature['data_type']
        dv_dict = {
            'BOOL': False,
            'INTEGER': 0,
            'ENUM': ''
        }
        v = dv_dict.get(t, None)
        if v is None:
            log.warning('Неизвестный тип даных: ' + t)
            return False
        else:
            if feature['name'] == 'online':
                return True
            else:
                return v

    def StateValue(self, id, feature):
        # {'key':'online','value':{"type": "BOOL", "bool_value": True}}
        State = self.DB[id]['States'][feature['name']]
        r = {}
        if feature['name'] == 'temperature':
            State = State * 10
        if feature['data_type'] == 'BOOL':
            r = {'key': feature['name'], 'value': {'type': 'BOOL', 'bool_value': bool(State)}}
        if feature['data_type'] == 'INTEGER':
            r = {'key': feature['name'], 'value': {'type': 'INTEGER', 'integer_value': int(State)}}
        if feature['data_type'] == 'ENUM':
            r = {'key': feature['name'], 'value': {'type': 'ENUM', 'enum_value': State}}
        log.debug('%s: %s', id, r)
        return r

    def do_mqtt_json_states_list(self, dl):
        DStat = {
            'devices': {}
        }
        if len(dl) == 0:
            dl = self.DB.keys()
        for id in dl:
            device = self.DB.get(id, None)
            if device is not None:
                if device['enabled']:
                    device_category = device.get('category', None)
                    if device_category is None:
                        device_category = 'relay'
                        self.DB[id]['category'] = device_category
                    DStat['devices'][id] = {}
                    features = self.categories.get(device_category)
                    if self.DB[id].get('States', None) is None:
                        self.DB[id]['States'] = {}
                    r = []
                    for ft in features:
                        state_value = self.DB[id]['States'].get(ft['name'], None)
                        if state_value is None:
                            if ft.get('required', False):
                                log.warning('отсутствует обязательное состояние сущности: ' + ft['name'])
                                self.DB[id]['States'][ft['name']] = self.DefaultValue(ft)
                        if self.DB[id]['States'].get(ft['name'], None) is not None:
                            r.append(self.StateValue(id, ft))
                            if ft['name'] == 'button_event':
                                self.DB[id]['States']['button_event'] = ''
                    DStat['devices'][id]['states'] = r
        #               if (s is None):
        #                  log('У объекта: '+id+'отсутствует информация о состояниях')
        #                  self.DB[id]['States']={}
        #                  self.DB[id]['States']['online']=True
        #               DStat['devices'][id]['states']=self.DeviceStates_mqttSber(id)

        if len(DStat['devices']) == 0:
            DStat['devices'] = {"root": {"states": [{"key": "online", "value": {"type": "BOOL", "bool_value": True}}]}}
        self.mqtt_json_states_list = json.dumps(DStat)
        log.debug("Отправка состояний в Sber: %s", self.mqtt_json_states_list)
        return self.mqtt_json_states_list

    def do_http_json_devices_list(self):
        Dev = {}
        Dev['devices'] = []
        x = []
        for k, v in self.DB.items():
            r = {}
            r['id'] = k
            r['name'] = v.get('name', '')
            r['default_name'] = v.get('default_name', '')
            r['nicknames'] = v.get('nicknames', [])
            r['home'] = v.get('home', '')
            r['room'] = v.get('room', '')
            r['groups'] = v.get('groops', [])
            r['model_id'] = v['model_id']
            r['category'] = v.get('category', '')
            r['hw_version'] = v.get('hw_version', '')
            r['sw_version'] = v.get('sw_version', '')
            x.append(r)
            Dev['devices'].append(r)
        self.http_json_devices_list = json.dumps({'devices': x})
        return self.http_json_devices_list

    def do_http_json_devices_list_2(self):
        return {'devices': self.DB}

    def get_ha_entity_data(self, entity_id):
        state = self.get_state(entity_id, 'on_off')
        entity_domain, entity_name = entity_id.split('.', 1)
        service = 'turn_on' if state else 'turn_off'
        data = {
            "entity_domain": entity_domain,
            "entity_name": entity_name,
            "service": service
        }
        return data