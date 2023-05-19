# cython: language_level=3

from numpy.random import default_rng
from numpy import sin, cos, linspace, hstack, pi, flip, newaxis

def random_path(position, radius, linger, *, random_state):
    random_state = default_rng() if random_state is None else random_state

    (x, y), r = position, radius

    xr = random_state.uniform(radius * .75, radius / .75)
    yr = random_state.uniform(radius * .75, radius / .75)
    steps = random_state.integers(15, 15 * linger + 1)
    angle = random_state.uniform(0, 2*pi)

    off = (pi / 2 - angle) % (2 * pi)
    space = linspace(off + 0, off + 2 * pi, steps)
    if random_state.random() > .5:
        space = flip(space)

    p = hstack([
        (xr * sin(space) + x - xr * cos(angle))[:, newaxis],
        (yr * cos(space) + y - yr * sin(angle))[:, newaxis],
    ]).clip(0 + .1, 25 - .1)

    noise = random_state.normal(loc=0, scale=.05, size=p.shape)
    noise[:1, :] = noise[-2:, :] = 0 # precise take-off & landing

    return p + noise
