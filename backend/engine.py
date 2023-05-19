#!/usr/bin/env python3

from argparse import ArgumentParser
from collections.abc import Generator
from dataclasses import dataclass
from functools import wraps
from io import BytesIO
from itertools import count, islice
from json import load as json_load
from math import isclose
from pathlib import Path

from yaml import safe_load as yaml_safe_load

from matplotlib.pyplot import subplots, show, close
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.path import Path as mpl_Path
from matplotlib.patches import RegularPolygon, PathPatch
from numpy import ndarray, clip
from numpy.random import default_rng
from scipy.ndimage import gaussian_filter

from backend.random_path import random_path #.paths will not import for some reason

pumped = lambda coro: wraps(coro)(lambda *a, **kw: [ci := coro(*a, **kw), next(ci)][0])

@pumped
def queen(default_worker_params, *, random_state=None):
    random_state = default_rng() if random_state is None else random_state

    hive = yield
    while True:
        params = {**default_worker_params, **hive.worker_params}
        new_bees = {
            k: worker(**params, random_state=random_state)
            for k, v in hive.workers.items()
            if v is None
        }
        hive = yield new_bees

@pumped
def worker(position, radius, linger, *, random_state=None):
    random_state = default_rng() if random_state is None else random_state
    path = map(tuple, random_path(position, radius, linger, random_state=random_state))
    _ = yield
    total_nectar = 0
    for p in path:
        total_nectar += yield p
    return total_nectar

@dataclass
class Hive:
    name          : str
    color         : str
    position      : tuple[int, int]
    description   : str
    queens        : dict[Generator]
    workers       : dict[Generator]
    worker_params : dict
    nectar        : float
    default_worker_params : dict

    @classmethod
    def from_yaml_entry(cls, entry, *, random_state=None):
        random_state = default_rng() if random_state is None else random_state

        name, color, position = entry['name'], entry['color'], entry['position']
        description = entry.get('description')

        position = tuple(position)

        default_worker_params = {'radius': 1, 'linger': 1}

        return cls(
            name=name,
            color=color,
            position=position,
            description=description,
            queens={
                0: queen(
                    {'position': position, **default_worker_params},
                    random_state=random_state,
                ),
            },
            workers={w: None for w in range(3)},
            worker_params={},
            default_worker_params=default_worker_params,
            nectar=3,
        )

    def __hash__(self):
        return hash(id(self))

@dataclass
class Field:
    nectar     : ndarray
    max_nectar : ndarray

    @classmethod
    def from_random(cls, *, random_state=None):
        random_state = default_rng() if random_state is None else random_state
        nectar = gaussian_filter(random_state.uniform(0, 1, size=(25, 25)), .5).round(2)
        return cls(nectar=nectar, max_nectar=nectar)

@dataclass
class Simulation:
    regrowth    : float
    collection  : float
    consumption : float
    safe_mode   : bool
    field       : Field
    hives       : set[Hive]

    @classmethod
    def from_config(cls, params_filename, hives_filename, *, random_state=None):
        random_state = default_rng() if random_state is None else random_state

        with open(params_filename) as f:
            params = json_load(f)
            regrowth, collection, consumption = params['regrowth'], params['collection'], params['consumption']
            safe_mode = params.get('safeMode', False)

        field = Field.from_random(random_state=random_state)
        with open(hives_filename) as f:
            hives = [
                Hive.from_yaml_entry(entry, random_state=random_state)
                for entry in yaml_safe_load(f)['hives']
            ]

        return cls(
            regrowth=regrowth,
            collection=collection,
            consumption=consumption,
            field=field,
            hives=hives,
            safe_mode=safe_mode,
        )

    def plot(self, worker_paths):
        fig, ax = subplots(figsize=(10, 10))
        ax.set_aspect('equal')

        cmap = LinearSegmentedColormap.from_list('honey', [(1, 1, 1), (197/255, 143/255, 0/255)])
        im = ax.pcolormesh(self.field.nectar, cmap=cmap, vmin=0, vmax=1)

        for h in self.hives:
            hive = RegularPolygon(
                h.position, 3, radius=.5, color=h.color, transform=ax.transData, zorder=10, ec='k', lw=.4
            )
            ax.add_artist(hive)

        for p in worker_paths.values():
            path = PathPatch(
                mpl_Path(p),
                fc='none', ec='black', lw=.5,
            )
            ax.add_artist(path)

        ax.axis('off')
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', pad_inches=0)
        close(fig)
        return buf.getvalue()

    @pumped
    def __call__(self, *, yield_plot=True, random_state):
        random_state = default_rng() if random_state is None else random_state

        worker_paths = {}

        _ = yield
        for step in count(1):
            self.field.nectar = clip(
                self.field.nectar * self.regrowth,
                0,
                self.field.max_nectar,
            )
            self.field.nectar += 1e-6 # epsilon
            for h in self.hives:
                for q in h.queens.values():
                    new_bees = q.send(h)
                    for k, v in new_bees.items():
                        if h.nectar - self.consumption < 0:
                            if self.safe_mode and all(w is None for w in h.workers.values()):
                                h.workers[k] = v # freebie to prevent collony collapse
                                h.nectar = 0
                            break
                        if h.workers[k] is not None:
                            continue
                        h.workers[k] = v
                        h.nectar -= self.consumption
                for k, w in h.workers.items():
                    if w is None: continue
                    try:
                        if w not in worker_paths:
                            worker_paths[w] = []
                            nectar = 0
                        else:
                            y, x = worker_paths[w][-1]
                            nectar = self.field.nectar[int(x), int(y)] * self.collection
                            self.field.nectar[int(x), int(y)] *= 1 - self.collection
                        worker_paths[w].append(w.send(nectar))
                    except StopIteration as e:
                        del worker_paths[w]
                        h.workers[k] = None
                        h.nectar += e.value
                for h in self.hives:
                    cleared_params = {*()}
                    for k in h.worker_params:
                        if isclose(h.worker_params[k], h.default_worker_params[k], abs_tol=.01):
                            cleared_params.add(k)
                        diff = h.worker_params[k] - h.default_worker_params[k]
                        h.worker_params[k] -= diff / 100
                    for k in cleared_params:
                        del h.worker_params[k]
                    h.nectar *= (1 - 1e-3)
            yield step, self.plot(worker_paths) if yield_plot else None

    def __repr__(self):
        return (
            f'Simulation('
                f'regrowth={self.regrowth!r}, '
                f'collection={self.collection!r}, '
                f'consumption={self.consumption!r}, '
                f'field=..., '
                f'hives={self.hives!r}'
            ')'
        )

if __name__ == '__main__':
    main()

parser = ArgumentParser()
parser.add_argument('params', type=Path, metavar='PARAMS_FILENAME')
parser.add_argument('hives', type=Path, metavar='HIVES_FILENAME')
parser.add_argument('-s', '--seed', type=int, default=0)
parser.add_argument('--steps', type=int, default=1_000)

def main():
    args = parser.parse_args()
    rng = default_rng(args.seed)
    sim = Simulation.from_config(args.params, args.hives, random_state=rng)

    for step, _ in islice(sim(yield_plot=False, random_state=rng), args.steps):
        if step % 100 == 0:
            print(f'#{step:<8}field mean {round(sim.field.nectar.mean(), 4)} total {round(sim.field.nectar.sum(), 4)}')
            for h in sim.hives:
                print(f'#{step:<8}hive {h.name} nectar {round(h.nectar, 4)}')
