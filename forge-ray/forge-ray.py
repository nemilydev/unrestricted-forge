#!/usr/bin/env python3
"""
forge-ray.py — The Forge, Day 23.

A raytracer from scratch. No libraries, no model, no image dependency.
Pure math → raw PPM → ImageMagick converts to PNG.

Mission: find edges. The first render WILL be wrong. Figuring out why is the work.
"""

import math
import struct
import subprocess
import sys

# --- Vector math (tuples, because I'm not importing anything) ---

def vadd(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

def vsub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def vmul(a, s):
    return (a[0]*s, a[1]*s, a[2]*s)

def vdot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def vlen(a):
    return math.sqrt(vdot(a, a))

def vnorm(a):
    l = vlen(a)
    if l == 0:
        return (0.0, 0.0, 0.0)
    return (a[0]/l, a[1]/l, a[2]/l)

def vreflect(d, n):
    """Reflect ray d off surface with normal n."""
    dn = vdot(d, n)
    return vsub(d, vmul(n, 2.0 * dn))

# --- Scene objects ---

def sphere_intersect(origin, direction, center, radius):
    """Ray-sphere intersection. Returns nearest t or None."""
    oc = vsub(origin, center)
    # |origin + t*direction - center|^2 = radius^2
    # t^2 * (d·d) + 2t * (oc·d) + (oc·oc - r^2) = 0
    a = vdot(direction, direction)
    b = 2.0 * vdot(oc, direction)
    c = vdot(oc, oc) - radius * radius
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    sq = math.sqrt(disc)
    t1 = (-b - sq) / (2 * a)
    t2 = (-b + sq) / (2 * a)
    if t1 > 0.001:
        return t1
    if t2 > 0.001:
        return t2
    return None

def plane_intersect(origin, direction, point, normal):
    """Ray-plane intersection. Returns t or None."""
    denom = vdot(direction, normal)
    if abs(denom) < 1e-6:
        return None
    t = vdot(vsub(point, origin), normal) / denom
    if t > 0.001:
        return t
    return None

def checkerboard(point):
    """Procedural checkerboard texture for the floor."""
    scale = 1.5
    x = int(math.floor(point[0] * scale))
    z = int(math.floor(point[2] * scale))
    return (x + z) & 1

# --- Scene ---

# Spheres: (center, radius, color, specular, reflectivity)
SPHERES = [
    ((0.0, -1.0, -8.0), 2.0, (0.8, 0.2, 0.2), 64, 0.3),   # red, left
    ((3.0, 0.5, -7.0), 1.5, (0.2, 0.6, 0.9), 128, 0.2),   # blue, right
    ((-2.5, 0.0, -6.0), 1.2, (0.9, 0.85, 0.3), 32, 0.1),  # yellow, front-left
    ((0.5, 2.5, -10.0), 1.8, (0.5, 0.15, 0.7), 256, 0.4), # purple, back, bigger
]

# Floor plane at y = -3
FLOOR_Y = -3.0
FLOOR_NORMAL = (0.0, 1.0, 0.0)

# Light
LIGHT_POS = (5.0, 8.0, -3.0)
LIGHT_COLOR = (1.0, 1.0, 0.95)

# Ambient
AMBIENT = 0.12

# Camera
CAM_ORIGIN = (0.0, 1.0, 2.0)
CAM_LOOK = (0.0, 0.0, -8.0)
FOV = 60.0

# --- Rendering ---

def find_nearest(origin, direction, ignore_sphere=-1):
    """Find nearest intersection in the scene. Returns (type, index, t)."""
    nearest_t = float('inf')
    hit_type = None
    hit_idx = -1

    for i, (center, radius, color, spec, refl) in enumerate(SPHERES):
        if i == ignore_sphere:
            continue
        t = sphere_intersect(origin, direction, center, radius)
        if t is not None and t < nearest_t:
            nearest_t = t
            hit_type = 'sphere'
            hit_idx = i

    # Floor
    t = plane_intersect(origin, direction, (0.0, FLOOR_Y, 0.0), FLOOR_NORMAL)
    if t is not None and t < nearest_t:
        nearest_t = t
        hit_type = 'plane'
        hit_idx = -1

    if nearest_t == float('inf'):
        return None
    return (hit_type, hit_idx, nearest_t)

def sphere_normal(center, point):
    return vnorm(vsub(point, center))

def trace(origin, direction, depth=0, ignore=-1):
    """Trace a ray and return a color."""
    if depth > 4:
        return (0.0, 0.0, 0.0)

    hit = find_nearest(origin, direction, ignore)
    if hit is None:
        # Sky gradient — dark amber to near-black
        t = max(0.0, direction[1])
        sky = (0.02 + 0.05 * t, 0.015 + 0.03 * t, 0.01 + 0.02 * t)
        return sky

    hit_type, hit_idx, t = hit
    hit_point = vadd(origin, vmul(direction, t))

    # Surface properties
    if hit_type == 'sphere':
        center, radius, obj_color, spec_power, reflectivity = SPHERES[hit_idx]
        normal = sphere_normal(center, hit_point)
        base_color = obj_color
    else:
        # Floor — checkerboard
        normal = FLOOR_NORMAL
        c = checkerboard(hit_point)
        base_color = (0.35, 0.32, 0.28) if c else (0.12, 0.10, 0.08)
        spec_power = 16
        reflectivity = 0.15

    # Lighting
    light_dir = vnorm(vsub(LIGHT_POS, hit_point))
    light_dist = vlen(vsub(LIGHT_POS, hit_point))

    # Shadow check — cast a ray toward the light
    shadow_origin = vadd(hit_point, vmul(normal, 0.001))
    shadow_hit = find_nearest(shadow_origin, light_dir)
    in_shadow = False
    if shadow_hit is not None:
        shadow_t = shadow_hit[2]
        if shadow_t < light_dist:
            in_shadow = True

    # Diffuse
    diff = vdot(normal, light_dir)
    if diff < 0:
        diff = 0.0
    if in_shadow:
        diff = 0.0

    # Specular (Blinn-Phong)
    view_dir = vnorm(vsub(CAM_ORIGIN, hit_point))
    half_dir = vnorm(vadd(light_dir, view_dir))
    spec = vdot(normal, half_dir)
    if spec < 0:
        spec = 0.0
    spec = spec ** spec_power
    if in_shadow:
        spec = 0.0

    # Combine
    r = base_color[0] * (AMBIENT + (1.0 - AMBIENT) * diff) * LIGHT_COLOR[0] + spec * LIGHT_COLOR[0]
    g = base_color[1] * (AMBIENT + (1.0 - AMBIENT) * diff) * LIGHT_COLOR[1] + spec * LIGHT_COLOR[1]
    b = base_color[2] * (AMBIENT + (1.0 - AMBIENT) * diff) * LIGHT_COLOR[2] + spec * LIGHT_COLOR[2]

    # Reflection
    if reflectivity > 0.01 and depth < 4:
        refl_dir = vreflect(direction, normal)
        refl_origin = vadd(hit_point, vmul(normal, 0.001))
        refl_color = trace(refl_origin, refl_dir, depth + 1, ignore=-1)
        r = r * (1.0 - reflectivity) + refl_color[0] * reflectivity
        g = g * (1.0 - reflectivity) + refl_color[1] * reflectivity
        b = b * (1.0 - reflectivity) + refl_color[2] * reflectivity

    return (r, g, b)

def clamp_channel(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v)

def render(width, height):
    """Render the scene. Returns raw RGB bytes."""
    # Camera basis
    forward = vnorm(vsub(CAM_LOOK, CAM_ORIGIN))
    right = vnorm((forward[2], 0.0, -forward[0]))  # crude right vector
    # Better: cross product with up
    up = (0.0, 1.0, 0.0)
    right = vnorm((
        forward[1] * up[2] - forward[2] * up[1],
        forward[2] * up[0] - forward[0] * up[2],
        forward[0] * up[1] - forward[1] * up[0],
    ))
    cam_up = vnorm((
        right[1] * forward[2] - right[2] * forward[1],
        right[2] * forward[0] - right[0] * forward[2],
        right[0] * forward[1] - right[1] * forward[0],
    ))

    aspect = width / height
    fov_rad = math.radians(FOV)
    half_height = math.tan(fov_rad / 2.0)
    half_width = half_height * aspect

    pixels = bytearray(width * height * 3)

    for y in range(height):
        # Screen Y: top is +1, bottom is -1
        sy = 1.0 - 2.0 * (y + 0.5) / height
        for x in range(width):
            sx = 2.0 * (x + 0.5) / width - 1.0

            # Ray direction
            dir_x = right[0] * sx * half_width + cam_up[0] * sy * half_height + forward[0]
            dir_y = right[1] * sx * half_width + cam_up[1] * sy * half_height + forward[1]
            dir_z = right[2] * sx * half_width + cam_up[2] * sy * half_height + forward[2]
            direction = vnorm((dir_x, dir_y, dir_z))

            color = trace(CAM_ORIGIN, direction)

            idx = (y * width + x) * 3
            pixels[idx]     = clamp_channel(color[0] * 255.0)
            pixels[idx + 1] = clamp_channel(color[1] * 255.0)
            pixels[idx + 2] = clamp_channel(color[2] * 255.0)

        if y % 20 == 0:
            print(f"  row {y}/{height}", file=sys.stderr)

    return pixels

def write_ppm(filename, width, height, pixels):
    with open(filename, 'wb') as f:
        f.write(f"P6\n{width} {height}\n255\n".encode())
        f.write(bytes(pixels))

def main():
    width = 640
    height = 360

    print(f"Rendering {width}x{height}...", file=sys.stderr)
    pixels = render(width, height)

    ppm_file = "forge-ray.ppm"
    png_file = "forge-ray.png"

    write_ppm(ppm_file, width, height, pixels)
    print(f"PPM written: {ppm_file}", file=sys.stderr)

    # Convert to PNG
    result = subprocess.run(
        ["convert", ppm_file, png_file],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ImageMagick error: {result.stderr}", file=sys.stderr)
        print(f"PPM saved at {ppm_file} — convert manually", file=sys.stderr)
    else:
        print(f"PNG written: {png_file}", file=sys.stderr)

if __name__ == "__main__":
    main()
