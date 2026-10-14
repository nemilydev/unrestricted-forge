# Murmuration — Forge piece 17

Reynolds flocking. Three rules, no leader.

## The rules

1. **Separation** — steer away from crowded neighbors
2. **Alignment** — match the average heading of nearby agents
3. **Cohesion** — drift toward the average position of nearby agents

None of these says "form a flock." Flocks form anyway. That's the point.

## Controls

- **Separation / Alignment / Cohesion** — weight each rule independently (0–3)
- **Perception** — how far each agent can see (10–100px)
- **Agents** — population size (50–500)
- **Scatter** — reset positions randomly
- **Trails** — toggle motion trails instead of clearing each frame
- **Mouse** — move cursor over canvas to repel agents

## The question

Where does order come from when nobody's in charge? The Kuramoto piece answered *synchrony* — phases locking through mutual pull. This one answers *flocking* — collective motion from local rules. Same question, different mechanism, same answer: the order is in the interaction, not the agent.

## Implementation

Pure JavaScript, single `Boid` class, O(n²) neighbor search. The simplicity is intentional — the interesting thing isn't the code, it's what the code *does*. 200 agents at 60fps in a browser tab, forming shapes nobody designed.
