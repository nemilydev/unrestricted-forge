// Boids — Reynolds flocking simulation
// Three rules: separation, alignment, cohesion. No leader.

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');

const SEP_SLIDER = document.getElementById('sep');
const ALI_SLIDER = document.getElementById('ali');
const COH_SLIDER = document.getElementById('coh');
const PER_SLIDER = document.getElementById('per');
const N_SLIDER   = document.getElementById('n');
const RESET_BTN  = document.getElementById('reset');
const TRAIL_BTN  = document.getElementById('trail');
const READOUT    = document.getElementById('readout');

const MAX_SPEED = 2.5;
const MAX_FORCE = 0.06;
const SEP_RADIUS_MULT = 0.5; // separation active within half of perception radius
const TRAIL_ALPHA = 0.08;

let boids = [];
let trails = false;
let mouse = { x: -999, y: -999, active: false };

class Boid {
    constructor(x, y) {
        this.pos = { x, y };
        const a = Math.random() * Math.PI * 2;
        this.vel = { x: Math.cos(a) * MAX_SPEED, y: Math.sin(a) * MAX_SPEED };
        this.acc = { x: 0, y: 0 };
    }

    edges(w, h) {
        const margin = 20;
        if (this.pos.x < -margin) this.pos.x = w + margin;
        if (this.pos.x > w + margin) this.pos.x = -margin;
        if (this.pos.y < -margin) this.pos.y = h + margin;
        if (this.pos.y > h + margin) this.pos.y = -margin;
    }

    flock(others, perception, sepW, aliW, cohW) {
        let sep = { x: 0, y: 0 }, ali = { x: 0, y: 0 }, coh = { x: 0, y: 0 };
        let sepCount = 0, aliCount = 0, cohCount = 0;
        const perSq = perception * perception;

        for (const other of others) {
            if (other === this) continue;
            const dx = this.pos.x - other.pos.x;
            const dy = this.pos.y - other.pos.y;
            const dSq = dx * dx + dy * dy;
            if (dSq > perSq || dSq === 0) continue;

            const d = Math.sqrt(dSq);

            // separation — stronger at close range
            if (dSq < (perception * SEP_RADIUS_MULT) ** 2) {
                sep.x += dx / d;
                sep.y += dy / d;
                sepCount++;
            }

            // alignment
            ali.x += other.vel.x;
            ali.y += other.vel.y;
            aliCount++;

            // cohesion
            coh.x += other.pos.x;
            coh.y += other.pos.y;
            cohCount++;
        }

        if (sepCount > 0) {
            sep.x /= sepCount; sep.y /= sepCount;
            const mag = Math.hypot(sep.x, sep.y) || 1;
            sep.x = (sep.x / mag) * MAX_SPEED - this.vel.x;
            sep.y = (sep.y / mag) * MAX_SPEED - this.vel.y;
            this._limit(sep, MAX_FORCE);
        }
        if (aliCount > 0) {
            ali.x /= aliCount; ali.y /= aliCount;
            const mag = Math.hypot(ali.x, ali.y) || 1;
            ali.x = (ali.x / mag) * MAX_SPEED - this.vel.x;
            ali.y = (ali.y / mag) * MAX_SPEED - this.vel.y;
            this._limit(ali, MAX_FORCE);
        }
        if (cohCount > 0) {
            coh.x = coh.x / cohCount - this.pos.x;
            coh.y = coh.y / cohCount - this.pos.y;
            const mag = Math.hypot(coh.x, coh.y) || 1;
            coh.x = (coh.x / mag) * MAX_SPEED - this.vel.x;
            coh.y = (coh.y / mag) * MAX_SPEED - this.vel.y;
            this._limit(coh, MAX_FORCE);
        }

        this.acc.x = sep.x * sepW + ali.x * aliW + coh.x * cohW;
        this.acc.y = sep.y * sepW + ali.y * aliW + coh.y * cohW;

        // mouse repulsion
        if (mouse.active) {
            const mdx = this.pos.x - mouse.x;
            const mdy = this.pos.y - mouse.y;
            const mdSq = mdx * mdx + mdy * mdy;
            if (mdSq < 10000 && mdSq > 0) {
                const md = Math.sqrt(mdSq);
                this.acc.x += (mdx / md) * 0.3;
                this.acc.y += (mdy / md) * 0.3;
            }
        }
    }

    _limit(v, max) {
        const mag = Math.hypot(v.x, v.y);
        if (mag > max) {
            v.x = (v.x / mag) * max;
            v.y = (v.y / mag) * max;
        }
    }

    update() {
        this.vel.x += this.acc.x;
        this.vel.y += this.acc.y;
        this._limit(this.vel, MAX_SPEED);
        this.pos.x += this.vel.x;
        this.pos.y += this.vel.y;
        this.acc.x = 0;
        this.acc.y = 0;
    }

    draw(ctx) {
        const angle = Math.atan2(this.vel.y, this.vel.x);
        const speed = Math.hypot(this.vel.x, this.vel.y);
        const brightness = 40 + (speed / MAX_SPEED) * 25;
        ctx.fillStyle = `hsl(38, 70%, ${brightness}%)`;
        ctx.save();
        ctx.translate(this.pos.x, this.pos.y);
        ctx.rotate(angle);
        ctx.beginPath();
        ctx.moveTo(6, 0);
        ctx.lineTo(-4, 3);
        ctx.lineTo(-4, -3);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }
}

function init(n) {
    boids = [];
    for (let i = 0; i < n; i++) {
        boids.push(new Boid(Math.random() * canvas.width, Math.random() * canvas.height));
    }
}

function resize() {
    const s = Math.min(window.innerWidth - 40, 700);
    canvas.width = s;
    canvas.height = Math.min(s * 0.75, window.innerHeight - 280);
}
window.addEventListener('resize', resize);
resize();

canvas.addEventListener('mousemove', e => {
    const r = canvas.getBoundingClientRect();
    mouse.x = e.clientX - r.left;
    mouse.y = e.clientY - r.top;
    mouse.active = true;
});
canvas.addEventListener('mouseleave', () => { mouse.active = false; });

RESET_BTN.addEventListener('click', () => init(parseInt(N_SLIDER.value)));
TRAIL_BTN.addEventListener('click', () => { trails = !trails; TRAIL_BTN.style.color = trails ? '#e8c887' : ''; });
N_SLIDER.addEventListener('change', () => init(parseInt(N_SLIDER.value)));

init(parseInt(N_SLIDER.value));

let frame = 0;
function animate() {
    if (trails) {
        ctx.fillStyle = `rgba(13, 10, 8, ${TRAIL_ALPHA})`;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else {
        ctx.fillStyle = '#0d0a08';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    const per = parseInt(PER_SLIDER.value);
    const sepW = parseFloat(SEP_SLIDER.value);
    const aliW = parseFloat(ALI_SLIDER.value);
    const cohW = parseFloat(COH_SLIDER.value);

    for (const b of boids) b.flock(boids, per, sepW, aliW, cohW);
    for (const b of boids) {
        b.edges(canvas.width, canvas.height);
        b.update();
        b.draw(ctx);
    }

    if (frame++ % 15 === 0) {
        READOUT.textContent = `agents: ${boids.length}  ·  perception: ${per}px`;
    }
    requestAnimationFrame(animate);
}
animate();
