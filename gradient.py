#!/usr/bin/env python3
"""Forge IX — Gradient.

A neural network from scratch: no numpy, no frameworks, pure stdlib Python.
The question this piece asks, like the seven before it: where does order come
from when nobody is in charge?

Here the answer is: from error. Nobody designs the internal representation.
Gradient descent walks the loss landscape and the features assemble themselves
out of the walking. Selection pressure, applied to matrices.

Architecture: configurable sizes, tanh hidden layers, sigmoid output by
default (linear_output=True gives tanh, which can speak negatives),
mean squared error, per-sample stochastic gradient descent with momentum.
Two lessons are baked into the code: full-batch updates with high momentum
collapse into the all-zero plateau, and unreachable targets (sigmoid vs
sin's negative half) look exactly like a training failure from the outside.

The training set is the classic liar: XOR. Not linearly separable.
A network without hidden layers cannot solve it, provably. If this one
learns it, the learning is real — you cannot memorize XOR by accident.
"""

import math
import random
import json

random.seed(20261017)


# ---------------------------------------------------------------- activation

def tanh(x):
    return math.tanh(x)


def dtanh_from_y(y):
    # derivative of tanh given the OUTPUT y (cheaper, no second exp)
    return 1.0 - y * y


def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


# ---------------------------------------------------------------- the network

class Layer:
    def __init__(self, n_in, n_out, kind):
        self.kind = kind                      # 'tanh' or 'sigmoid'
        # Xavier-ish init scaled for tanh
        scale = math.sqrt(1.0 / n_in)
        self.w = [[random.uniform(-scale, scale) for _ in range(n_in)]
                  for _ in range(n_out)]
        self.b = [0.0] * n_out
        # last activations, kept for backward pass
        self.x = None       # inputs
        self.z = None       # pre-activations
        self.y = None       # outputs

    def forward(self, x):
        self.x = x
        self.z = []
        self.y = []
        for j in range(len(self.b)):
            s = self.b[j]
            wj = self.w[j]
            for i in range(len(x)):
                s += wj[i] * x[i]
            self.z.append(s)
            f = tanh if self.kind == 'tanh' else sigmoid
            self.y.append(f(s))
        return self.y

    def backward(self, grad_y):
        """grad_y: dLoss/dOutput for each neuron of this layer.
        Returns dLoss/dInput for the layer before, and stores weight grads."""
        n_in = len(self.x)
        self.dw = [[0.0] * n_in for _ in self.w]
        self.db = [0.0] * len(self.b)
        grad_x = [0.0] * n_in
        for j, yj in enumerate(self.y):
            if self.kind == 'tanh':
                dz = grad_y[j] * dtanh_from_y(yj)
            else:
                dz = grad_y[j] * yj * (1.0 - yj)
            self.db[j] += dz
            wj = self.w[j]
            dj = self.dw[j]
            x = self.x
            for i in range(n_in):
                dj[i] += dz * x[i]
                grad_x[i] += dz * wj[i]
        return grad_x


class Network:
    def __init__(self, sizes, linear_output=False):
        self.layers = []
        for k in range(len(sizes) - 1):
            kind = 'tanh' if k < len(sizes) - 2 else 'sigmoid'
            if linear_output and k == len(sizes) - 2:
                kind = 'tanh'  # tanh reaches [-1, 1]; sigmoid cannot go negative
            self.layers.append(Layer(sizes[k], sizes[k + 1], kind))

    def forward(self, x):
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def backward(self, target):
        # MSE loss: L = mean((y - t)^2)
        out = self.layers[-1].y
        grad = [2.0 * (out[i] - target[i]) / len(out) for i in range(len(out))]
        for layer in reversed(self.layers):
            grad = layer.backward(grad)

    def step(self, lr, momentum):
        for layer in self.layers:
            if not hasattr(layer, 'vw'):
                layer.vw = [[0.0] * len(r) for r in layer.w]
                layer.vb = [0.0] * len(layer.b)
            for j in range(len(layer.w)):
                wj, dj, vwj = layer.w[j], layer.dw[j], layer.vw[j]
                for i in range(len(wj)):
                    vwj[i] = momentum * vwj[i] - lr * dj[i]
                    wj[i] += vwj[i]
            for j in range(len(layer.b)):
                layer.vb[j] = momentum * layer.vb[j] - lr * layer.db[j]
                layer.b[j] += layer.vb[j]


# ---------------------------------------------------------------- training

def train():
    net = Network([2, 8, 8, 1])
    data = [([0.0, 0.0], [0.0]), ([0.0, 1.0], [1.0]),
            ([1.0, 0.0], [1.0]), ([1.0, 1.0], [0.0])]

    lr, momentum = 0.8, 0.9
    history = []
    for epoch in range(4001):
        # stochastic: one sample at a time, shuffled
        order = list(range(len(data)))
        random.shuffle(order)
        for k in order:
            x, t = data[k]
            net.forward(x)
            net.backward(t)
            net.step(lr, momentum)
        if epoch % 200 == 0:
            losses = []
            for x, t in data:
                y = net.forward(x)
                losses.append((y[0] - t[0]) ** 2)
            mse = sum(losses) / len(losses)
            history.append((epoch, mse))
    return net, history


def report(net, history):
    print("loss curve (epoch, mse):")
    for e, l in history:
        print(f"  {e:>5}  {l:.6f}")
    print("\ntruth table, learned:")
    for x, t in [([0.0, 0.0], 0.0), ([0.0, 1.0], 1.0),
                 ([1.0, 0.0], 1.0), ([1.0, 1.0], 0.0)]:
        y = net.forward(x)[0]
        ok = "OK " if abs(y - t) < 0.1 else "MISS"
        print(f"  {int(x[0])} xor {int(x[1])} -> {y:.4f}  (want {t:.0f})  {ok}")

    # the interesting part: what did the hidden layer learn?
    print("\nhidden layer representations (layer 1, 8 units, tanh):")
    for x, _ in [([0.0, 0.0], None), ([0.0, 1.0], None),
                 ([1.0, 0.0], None), ([1.0, 1.0], None)]:
        h = net.layers[0].forward(x)
        cells = "".join("#" if v > 0.3 else ("+" if v > 0.0 else ".") for v in h)
        print(f"  ({int(x[0])},{int(x[1])})  {cells}")


if __name__ == '__main__':
    net, history = train()
    report(net, history)
