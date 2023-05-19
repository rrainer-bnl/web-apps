from asyncio import sleep as aio_sleep
from base64 import b64encode
from enum import Enum
from json import dumps
from collections.abc import Callable, Generator
from contextlib import asynccontextmanager
from dataclasses import is_dataclass, asdict
from datetime import datetime
from logging import getLogger, basicConfig, INFO
from io import BytesIO
from pathlib import Path

from anyio import create_task_group
from yaml import safe_load
from asyncinotify import Inotify, Mask

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute
from starlette.responses import JSONResponse, StreamingResponse, PlainTextResponse
from starlette.websockets import WebSocket

from numpy import ndarray
from numpy.random import default_rng

from .engine import Simulation

logger = getLogger(__name__)
basicConfig(level=INFO)

class Response(JSONResponse):
    @classmethod
    def _default(cls, obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, Enum):
            return obj.name
        if isinstance(obj, ndarray):
            return obj.tolist()
        if isinstance(obj, Callable):
            return obj.__name__

    def render(self, content):
        return dumps(content, default=self._default).encode('utf-8')

def failure(message, **details):
    return Response({'error': message, **details}, status_code=400)

def success(**details):
    return Response(details)

async def test(request):
    return success(status='Ok!')

async def status(request):
    global sim
    if sim is None:
        return failure(message='simulation has not started')
    return success(hives=[
        {
            'name': h.name,
            'description': h.description,
            'color': h.color,
            'position': h.position,
            'workers': {
                'active': sum(w is not None for w in h.workers.values()),
                'total': len(h.workers),
            },
            'nectar': h.nectar,
            'directions': {
                'default': h.default_worker_params,
                'ordered': h.worker_params,
            },
        }
        for h in sim.hives
    ])

async def plot(request):
    global plot
    if plot is None:
        return failure(message='simulation has not yet started')
    return StreamingResponse(content=BytesIO(plot), media_type='image/png')

async def direct(request):
    global sim
    if sim is None:
        return failure(message='simulation has not yet started')
    try:
        body = await request.json()
    except Exception:
        return failure('bad or missing payload')
    if (name := body.get('name')) is None:
        return failure('must supply `name` in payload')
    radius, linger = body.get('radius'), body.get('linger')
    if radius is None and linger is None:
        return failure('must supply `radius` or `linger` in payload')
    if radius is not None:
        try:
            radius = float(radius)
        except Exception:
            return failure('radius must be numeric value')
    if linger is not None:
        try:
            linger = float(linger)
        except Exception:
            return failure('linger must be numeric value')
    for h in sim.hives:
        if h.name == name:
            if radius is not None:
                h.worker_params['radius'] = radius
            if linger is not None:
                h.worker_params['linger'] = linger
            return success(status='Ok!')
    return failure(message='no hive found by that name')

async def ws(scope, receive, send):
    websocket = Websocket(scope=scope, recieve=receive, send=send)
    await websocket.accept()
    await websocket.send_json({'test': 'success'})
    await websocket.close()

routes = [
    Route('/direct', direct, methods=['POST']),
    Route('/status', status, methods=['GET']),
    Route('/plot', plot, methods=['GET']),
    Route('/test', test, methods=['GET']),
    WebSocketRoute('/ws', ws),
]

sim, sim_coro, step, plot = None, None, None, None

@asynccontextmanager
async def lifespan(app):
    async with create_task_group() as g:
        tasks = [
            create_watcher(
                params_filename=Path(__file__).parent / 'params.json',
                hives_filename=Path(__file__).parent / 'hives.yml'
            ),
            create_ticker(.25),
        ]
        for t in tasks:
            g.start_soon(t)
        yield
        g.cancel_scope.cancel()

def create_watcher(params_filename, hives_filename):
    async def task():
        async def wait(inotify):
            async for event in inotify:
                return event
        while True:
            global sim, sim_coro, step, plot
            sim = Simulation.from_config(
                params_filename,
                hives_filename,
                random_state=default_rng(0),
            )
            sim_coro = sim(random_state=default_rng(0))
            step, plot = None, None
            with Inotify() as inotify:
                mask = Mask.MODIFY | Mask.CREATE | Mask.DELETE | Mask.ATTRIB
                inotify.add_watch(params_filename, mask)
                inotify.add_watch(hives_filename, mask)
                event = await wait(inotify)
                print(f'{event = }')
    return task

def create_ticker(wait):
    async def task():
        while True:
            global sim_coro, step, plot
            if sim_coro is not None:
                try:
                    step, plot = next(sim_coro)
                except StopIteration:
                    break
            await aio_sleep(wait)
    return task

app = Starlette(
    debug=True,
    routes=routes,
    lifespan=lifespan,
)
