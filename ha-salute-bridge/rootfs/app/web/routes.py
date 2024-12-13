import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from models.api import DevicesEditModel

router = APIRouter()

templates = Jinja2Templates(directory="../app/templates")

async def send_mqtt_conf(mqtt_queue, data):
    await mqtt_queue.put({"type": "conf", "data": data})


@router.get("/")
async def main(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html"
    )


@router.get("/api/v2/devices")
async def devices_list(request: Request):
    return request.state.devices.do_http_json_devices_list_2()


@router.post("/api/v2/devices")
async def update_device(request: Request, devices: DevicesEditModel):
    logging.debug('Меняем данные для %s', str(devices.devices))
    for i in devices.devices:
        for id, prop in i.items():
            logging.debug(id + ':' + str(prop))
            request.state.devices.update(id, prop)
    await send_mqtt_conf(request.state.mqtt_queue, request.state.devices.do_mqtt_json_devices_list())
    request.state.devices.save_DB()