# Soft Life — Forge piece 18

A multi-rule cellular automaton on a shared grid. Four rules, one canvas, switchable at runtime.

## Rules

1. **Gray-Scott** — reaction-diffusion. Two chemicals, one equation, patterns that look alive. F and k control morphology — spots, stripes, mazes, chaos.
2. **Conway (B3/S23)** — the classic Game of Life. Live cell with 2-3 neighbors survives, dead cell with exactly 3 births.
3. **HighLife (B36/S23)** — Conway's cousin. Same as Conway but dead cells with 6 neighbors also birth — produces replicators.
4. **Wireworld** — a cellular clock. Electrons flow along wires. The simplest model of a circuit that still feels like one.

## The question

Each rule is a different answer to: *where does pattern come from when nobody's designing it?*

Gray-Scott: from the dance of two chemicals diffusing and reacting.
Conway: from a one-line rule applied everywhere equally.
Wireworld: from the geometry of the wire — the pattern is the circuit.

## Interaction

Click and drag on the canvas to draw — paint cells in Conway, seed chemicals in Gray-Scott, lay wire in Wireworld. Sliders control simulation speed and Gray-Scott's F/k parameters.

## Throughline

This is the eighth Forge piece, continuing the investigation: where does order come from when nobody's in charge? Kuramoto said "coupling." Boids said "three local rules." Soft Life says "it depends on the rule, but the rule is always local."
