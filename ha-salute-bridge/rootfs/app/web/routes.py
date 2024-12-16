import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from models.api import DevicesEditModel, FeatureEditModel

router = APIRouter()

templates = Jinja2Templates(directory="../app/templates")

async def send_mqtt_conf(mqtt_queue):
    await mqtt_queue.put({"type": "conf"})


@router.get("/")
async def main(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html"
    )


@router.get("/api/v2/devices", response_class=JSONResponse)
async def devices_list(request: Request):
     data = request.state.devices.as_dict()
     return JSONResponse(data)


@router.post("/api/v2/devices")
async def update_device(request: Request, devices: DevicesEditModel):
    logging.debug('Меняем данные для %s', devices.devices)
    for i in devices.devices:
        for entity_id, prop in i.items():
            logging.debug('%s: %s', entity_id, prop)
            request.state.devices.update(entity_id, prop)
    await send_mqtt_conf(request.state.mqtt_queue)
    request.state.devices.save()


@router.post("/api/v2/device/features")
async def update_device(request: Request, feature: FeatureEditModel):
    logging.debug('Меняем данные для %s', feature)
    if feature.entity_id in request.state.devices.keys():
        device = request.state.devices[feature.entity_id]
        if device.features is None:
            device.features = []
        if feature.state:
            if feature.feature not in device.features:
                device.features.append(feature.feature)
        else:
            if feature.feature in device.features:
                device.features.remove(feature.feature)
        request.state.devices.update(feature.entity_id, device)
        await send_mqtt_conf(request.state.mqtt_queue)
        request.state.devices.save()