import json
import logging as log


def json_read(fname):
    try:
        with open(fname,'r', encoding='utf-8') as f:
            try:
                r = json.loads(f.read())
            except:
                r = {}
                log.error('!!! Неверная конфигурация в файле: %s', f)
            return r
    except FileNotFoundError:
        return {}

def json_write(fname, data):
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True)