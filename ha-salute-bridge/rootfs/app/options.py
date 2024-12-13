import logging as log

from const import OPTIONS_FILENAME
from utils import json_read, json_write



def load_options():
    return json_read(OPTIONS_FILENAME)


def options_change(options, key, val):
    t = options.get(key, None)
    if t is None:
        log.info('В настройках отсутствует параметр: %s (добавляю.)', key)
    if t != val:
        options[key] = val
        log.info('В настройках изменился параметр: %s с %s на %s (обновляю и сохраняю).', key, t, val)
        json_write(OPTIONS_FILENAME, options)
