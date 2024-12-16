function Init() {
    AddBlok('<h1>SberGate version: 1.0.15</h1>')
    AddBlok('<a href="index.html">Перейти к настройкам СберАгента</a></p>')
    AddBlok('<a href="SberGate.log">Скачать SberGate.log</a></p>')
    AddBlok('<h2>Команды:</h2>')
//   AddBlok('<button class="btn">&#128465; Удалить</button>')
    AddBlok('<button id="DB_delete" onclick="RunCmd(this.id)">   &#128465; Удалить базу устройств</button><button id="exit" onclick="RunCmd(this.id)">Выход</button>')
    AddBlok('<h2>Устройства:</h2>', 'alert')
    apiGet()
}

function AddBlok(str, CN) {
    let div = document.createElement('div');
    if (CN) {
        div.className = CN;
    }
    div.innerHTML = str;
    let el = document.getElementById('root');
    if (el) {
        el.append(div)
    }
//   document.body.append(div);
}

function RunCmd(id, opt) {
    alert(id + ':' + opt);
    let s = {'command': id}
    apiSend(s, '/api/v2/command');
}


function ChangeDev(d) {
    let t = {};
    let s = {};
    t[d.dataset.id] = {}
    t[d.dataset.id]['enabled'] = d.checked;
    s['devices'] = [];
    s['devices'].push(t);
    apiSend(s, '/api/v2/devices');
}


function ChangeFeatures(d) {
    let s = {};
    s['entity_id'] = d.dataset.id;
    s['feature'] = d.dataset.feature;
    s['state'] = d.checked;
    apiSend(s, '/api/v2/device/features');
}

function UpdateDeviceList(d) {
    let f = {
        'enabled': 'Включено',
        'home': 'Дом',
        'room': 'Комната',
        'id': 'ID',
        'name': 'Имя',
        'model': 'Модель',
        'state': 'Состояние',
        'attributes': 'Атрибуты',
        'features': 'Функции устройства'
    }
    // {
    //   "entity_id": "vykliuchatel_gostinnaia_left",
    //   "category": "light",
    //   "enabled": null,
    //   "name": "Бар",
    //   "state": "off",
    //   "model": "light",
    //   "attributes": null
    // },
    let table = document.getElementById('devices');
    if (!table) {
        table = document.createElement('table');
        table.id = 'devices';
        let pel = document.getElementById('root');
        pel.append(table);
    }

    let thead = document.createElement('thead');
    let tbody = document.createElement('tbody');

    let thead_row = document.createElement('tr');
    for (let k in f) {
        let el = document.createElement('th');
        el.innerHTML = f[k];
        thead_row.append(el)
    }
    thead.appendChild(thead_row);

    for (let i in d) {
        let tbody_row = document.createElement('tr');
        for (let k in f) {
            let el = document.createElement('td');
            let r = '';
            switch (k) {
                case 'id':
                    r = d[i]["category"] + "." + d[i]["entity_id"];
                    break;
                case 'enabled':
                    if (d[i][k]) {
                        r = '<input type="checkbox" data-id="' + i + '" checked onchange=ChangeDev(this)>';
                    } else {
                        r = '<input type="checkbox" data-id="' + i + '" onchange=ChangeDev(this)>';
                    }
                    break;
                case 'attributes':
                    if (d[i]['attributes']) {
                        r = JSON.stringify(d[i]['attributes']);
                    }
                    break;
                case 'features':
                    let features = d[i]["features"];
                    if (features == null) features = [];
                    if (d[i]["model"] === "light") {
                        r = '<input type="checkbox" data-id="' + i +
                            '" data-feature="brightness" '+ (features.includes("brightness") ? "checked" : "") +
                            ' onchange=ChangeFeatures(this)><label for="' + i +'">brightness</label>';
                    }
                    break;
                default:
                    r = d[i][k];
                    break;
            }
            el.innerHTML = r;
            tbody_row.append(el)
        }
        tbody.appendChild(tbody_row);
    }


    table.appendChild(thead);
    table.appendChild(tbody);
//   document.getElementById('body').appendChild(table);
//   for (let k in d['devices']){
//      let v=d['devices'][k];
//      AddBlok(v['id']+':'+v['name']);
//   }
}

function Res_Processing(Res) {
    console.log(Res);
}

function apiGet_url(url) {
    let xhr = new XMLHttpRequest();
    xhr.open('GET', url);
    xhr.send();
    xhr.onload = function () {
        if (xhr.status == 200) {
//         alert(`Готово, получили ${xhr.response.length} байт`);
            Res_Processing(xhr.response);
        } else { // если всё прошло гладко, выводим результат
            console.log(`Ошибка ${xhr.status}: ${xhr.statusText}`); // Например, 404: Not Found
        }
    };
    xhr.onprogress = function (event) {
        if (event.lengthComputable) {
            console.log(`Получено ${event.loaded} из ${event.total} байт`);
        } else {
            console.log(`Получено ${event.loaded} байт`); // если в ответе нет заголовка Content-Length
        }
    };
    xhr.onerror = function () {
        console.log("Запрос не удался");
    };
}

function apiGet() {
    let xhr = new XMLHttpRequest();
    xhr.open('GET', '/api/v2/devices');
    xhr.send();
    xhr.onload = function () {
        if (xhr.status == 200) {
//         alert(`Готово, получили ${xhr.response.length} байт`);
            UpdateDeviceList(JSON.parse(xhr.response))
        } else { // если всё прошло гладко, выводим результат
            console.log(`Ошибка ${xhr.status}: ${xhr.statusText}`); // Например, 404: Not Found
        }
    };
    xhr.onprogress = function (event) {
        if (event.lengthComputable) {
            console.log(`Получено ${event.loaded} из ${event.total} байт`);
        } else {
            console.log(`Получено ${event.loaded} байт`); // если в ответе нет заголовка Content-Length
        }
    };
    xhr.onerror = function () {
        console.log("Запрос не удался");
    };
}

function apiSend(d, api) { //console.log(d);
    if (typeof api == "undefined") {
        api = '/api/v2/devices';
    }
    let xhr = new XMLHttpRequest();
    let json = JSON.stringify(d);
    xhr.open('POST', api, true);
    xhr.setRequestHeader('Content-type', 'application/json; charset=utf-8');
    ///xhr.onreadystatechange = ...;
    xhr.send(json);
}