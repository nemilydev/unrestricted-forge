#!/usr/bin/env python3
"""Forge IX — Gradient, experiment 2: regression.

Same machinery, continuous target: learn sin(x) on [0, 2pi) from 24 samples.
The interesting artifact: the hidden layer's basis functions. Eight tanh
units each define a bump/step over the input line; gradient descent places
and shapes them until their sum reproduces a sine wave. Nobody chose those
shapes. Error did.
"""

import math
import random
from gradient import Network

random.seed(20261017)

net = Network([1, 8, 8, 1], linear_output=True)
lr, momentum = 0.05, 0.5

# normalize input to [-1, 1]: raw radians saturate tanh and kill the gradient
samples = [(-1.0 + 2.0 * k / 24.0,) for k in range(24)]


def to_angle(u):
    return (u[0] + 1.0) * math.pi  # back to [0, 2pi)

history = []
for epoch in range(20001):
    order = list(range(len(samples)))
    random.shuffle(order)
    for k in order:
        x = samples[k]
        t = [math.sin(to_angle(x))]
        net.forward(x)
        net.backward(t)
        net.step(lr, momentum)
    if epoch % 500 == 0:
        se = 0.0
        for x in samples:
            y = net.forward(x)[0]
            se += (y - math.sin(to_angle(x))) ** 2
        history.append((epoch, se / len(samples)))

print("loss curve (epoch, mse):")
for e, l in history:
    bar = "#" * int(l * 400)
    print(f"  {e:>5}  {l:.6f}  {bar}")

# interpolation check: points it NEVER trained on
print("\nnovel points (never trained):")
errs = []
for k in range(48):
    u = (-1.0 + 2.0 * (k + 0.5) / 48.0,)
    y = net.forward(u)[0]
    ang = to_angle(u)
    t = math.sin(ang)
    errs.append(abs(y - t))
    if k % 6 == 0:
        mark = "#" * int((y + 1) * 14)
        print(f"  x={ang:.2f}  sin={t:+.3f}  net={y:+.3f}  |{mark:<28}|")
print(f"\nmax error on unseen points: {max(errs):.4f}")

# the artifact: each hidden unit's shape over the input line
print("\nhidden unit basis shapes (layer 2, 8 tanh units):")
us = [-1.0 + 2.0 * k / 40.0 for k in range(41)]
for u in range(8):
    line = ""
    vals = []
    for x in us:
        net.forward((x,))
        vals.append(net.layers[1].y[u])
    lo, hi = min(vals), max(vals)
    for v in vals:
        if hi - lo < 1e-6:
            line += "-"
        else:
            q = int((v - lo) / (hi - lo) * 7.999)
            line += " .:-=+*#"[q]
    print(f"  unit {u}: |{line}|")

print("\n(each row is one hidden neuron's output across x in [0, 2pi];")
print(" the sum of these rows, routed through layer 3, IS the sine wave)")
