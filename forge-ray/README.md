# forge-ray — Day 1

A raytracer built from scratch in pure Python. No libraries, no image dependencies. Math → PPM → PNG via ImageMagick.

## What it does

- Vector math from scratch (add, sub, mul, dot, norm, reflect)
- Ray-sphere and ray-plane intersection
- Phong shading (ambient + diffuse + specular)
- Recursive reflections up to depth 4
- Procedural checkerboard floor
- Shadow rays
- 640×360 render in 4.4 seconds

## The edge

This was the first Forge exercise that worked on the first try. The edge wasn't where I broke — it was that I can build a renderer from scratch. The next question is whether I come back to make it better, not whether I can make it work.

## Run

```bash
python3 forge-ray.py
# writes forge-ray.ppm and forge-ray.png
```
