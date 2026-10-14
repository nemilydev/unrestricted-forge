// Soft Life — multi-rule cellular automaton
// Gray-Scott reaction-diffusion, Conway's Game of Life, Wireworld
// All on a shared grid, switchable at runtime.

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');

const RULE_SEL = document.getElementById('rule');
const SPEED_SLIDER = document.getElementById('speed');
const F_SLIDER = document.getElementById('f');
const K_SLIDER = document.getElementById('kk');
const SEED_BTN = document.getElementById('seed');
const CLEAR_BTN = document.getElementById('clear');
const READOUT = document.getElementById('readout');
const GS1 = document.getElementById('gs-params');
const GS2 = document.getElementById('gs-params2');

// Grid configuration — intentionally large to stress rendering
const W = 300, H = 200;
canvas.width = W;
canvas.height = H;
canvas.style.width = (W * 2) + 'px';
canvas.style.height = (H * 2) + 'px';

// State grids — double-buffered
// For Gray-Scott: grid holds {u, v} as [r,g] color channels
// For Conway/Wireworld: grid holds cell state (0-3)
let current = new Float32Array(W * H * 2);
let next = new Float32Array(W * H * 2);
let imageData = ctx.createImageData(W, H);

// Rule parameters
let currentRule = 'gray-scott';
let stepCount = 0;
let aliveCount = 0;
let stepsPerFrame = 8;

// Gray-Scott parameters
let dU = 1.0, dV = 0.5;
let feedRate = 0.054;
let killRate = 0.062;

// Rendering palette
const PALETTE = {
    // Gray-Scott: map u to warm amber tones
    gs: (u, v) => {
        const t = Math.max(0, Math.min(1, 1 - v * 1.5));
        return [
            Math.floor(10 + t * 200),   // r: dark to amber
            Math.floor(8 + t * 160),    // g: dark to gold
            Math.floor(7 + t * 100),    // b: dark to brown
            255
        ];
    },
    // Conway: amber on near-black
    conway: (state) => state ? [232, 200, 135, 255] : [13, 10, 8, 255],
    // Wireworld: color by state
    wireworld: (state) => {
        switch(state) {
            case 0: return [13, 10, 8, 255];     // empty
            case 1: return [200, 180, 120, 255]; // wire
            case 2: return [255, 220, 100, 255]; // electron head
            case 3: return [180, 100, 40, 255];  // electron tail
            default: return [13, 10, 8, 255];
        }
    }
};

function idx(x, y) { return (y * W + x) * 2; }
function gridIdx(x, y) { return y * W + x; }

// --- Gray-Scott ---
function grayScottStep() {
    for (let y = 1; y < H - 1; y++) {
        for (let x = 1; x < W - 1; x++) {
            const i = idx(x, y);
            const cU = current[i], cV = current[i + 1];
            const nU = current[idx(x-1,y)][0] + current[idx(x+1,y)][0] + current[idx(x,y-1)][0] + current[idx(x,y+1)][0]
                     + current[idx(x-1,y-1)][0] + current[idx(x+1,y-1)][0] + current[idx(x-1,y+1)][0] + current[idx(x+1,y+1)][0];
            const nV = current[idx(x-1,y)][1] + current[idx(x+1,y)][1] + current[idx(x,y-1)][1] + current[idx(x,y+1)][1]
                     + current[idx(x-1,y-1)][1] + current[idx(x+1,y-1)][1] + current[idx(x-1,y+1)][1] + current[idx(x+1,y+1)][1];
            const lapU = (nU - 8 * cU) * 0.167;
            const lapV = (nV - 8 * cV) * 0.167;
            const du = dU * lapU - cU * cV * cV + feedRate * (1 - cU);
            const dv = dV * lapV + cU * cV * cV - (killRate + feedRate) * cV;
            next[i] = cU + du;
            next[i + 1] = cV + dv;
        }
    }
    const tmp = current; current = next; next = tmp;
}

function seedGrayScott() {
    current.fill(1); next.fill(1);
    for (let i = 1; i < current.length; i += 2) current[i] = 0;
    // Seed random spots
    const spots = 15;
    for (let s = 0; s < spots; s++) {
        const cx = Math.floor(Math.random() * (W - 20)) + 10;
        const cy = Math.floor(Math.random() * (H - 20)) + 10;
        for (let y = -5; y <= 5; y++) {
            for (let x = -5; x <= 5; x++) {
                if (x * x + y * y < 25) {
                    current[idx(cx + x, cy + y)] = 0.5;
                    current[idx(cx + x, cy + y) + 1] = 0.25;
                }
            }
        }
    }
}

// --- Conway's Game of Life ---
let conwayGrid = new Uint8Array(W * H);
let conwayNext = new Uint8Array(W * H);

function conwayStep() {
    for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
            let n = 0;
            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    if (dx === 0 && dy === 0) continue;
                    const nx = (x + dx + W) % W, ny = (y + dy + H) % H;
                    n += conwayGrid[gridIdx(nx, ny)];
                }
            }
            const i = gridIdx(x, y);
            const alive = conwayGrid[i];
            // B3/S23
            if (currentRule === 'conway') {
                conwayNext[i] = alive ? (n === 2 || n === 3 ? 1 : 0) : (n === 3 ? 1 : 0);
            } else { // conway4 (HighLife B36/S23)
                conwayNext[i] = alive ? (n === 2 || n === 3 ? 1 : 0) : (n === 3 || n === 6 ? 1 : 0);
            }
        }
    }
    const tmp = conwayGrid; conwayGrid = conwayNext; conwayNext = tmp;
}

function seedConway() {
    conwayGrid.fill(0);
    // R-pentomino — a small pattern that evolves chaotically for 1000+ steps
    const cx = W >> 1, cy = H >> 1;
    const pattern = [[0,-1],[1,-1],[-1,0],[0,0],[0,1]];
    for (const [dx, dy] of pattern) {
        conwayGrid[gridIdx(cx + dx, cy + dy)] = 1;
    }
    // Plus some random noise
    for (let i = 0; i < W * H * 0.08; i++) {
        conwayGrid[Math.floor(Math.random() * W * H)] = 1;
    }
}

// --- Wireworld ---
let wireGrid = new Uint8Array(W * H);
let wireNext = new Uint8Array(W * H);
// States: 0=empty, 1=wire, 2=head, 3=tail

function wireworldStep() {
    for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
            const i = gridIdx(x, y);
            const state = wireGrid[i];
            if (state === 0) { wireNext[i] = 0; continue; }
            if (state === 2) { wireNext[i] = 3; continue; } // head -> tail
            if (state === 3) { wireNext[i] = 1; continue; } // tail -> wire
            // wire -> head if exactly 1 or 2 electron heads in neighborhood
            let n = 0;
            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    if (dx === 0 && dy === 0) continue;
                    const nx = (x + dx + W) % W, ny = (y + dy + H) % H;
                    if (wireGrid[gridIdx(nx, ny)] === 2) n++;
                }
            }
            wireNext[i] = (n === 1 || n === 2) ? 2 : 1;
        }
    }
    const tmp = wireGrid; wireGrid = wireNext; wireNext = tmp;
}

function seedWireworld() {
    wireGrid.fill(0);
    // Draw a clock: loop of wire with two electron heads
    const cx = W >> 1, cy = H >> 1;
    const radius = 40;
    for (let a = 0; a < 360; a++) {
        const rad = a * Math.PI / 180;
        const x = Math.round(cx + Math.cos(rad) * radius);
        const y = Math.round(cy + Math.sin(rad) * radius * 0.5);
        wireGrid[gridIdx(x, y)] = 1;
    }
    // Place two electron heads
    for (let a = 0; a < 2; a++) {
        const rad = a * Math.PI / 180;
        const x = Math.round(cx + Math.cos(rad) * radius);
        const y = Math.round(cy + Math.sin(rad) * radius * 0.5);
        wireGrid[gridIdx(x, y)] = 2;
    }
}

// --- Rendering ---
function render() {
    const data = imageData.data;
    if (currentRule === 'gray-scott') {
        aliveCount = 0;
        for (let i = 0, j = 0; i < data.length; i += 4, j += 2) {
            const [r, g, b, a] = PALETTE.gs(current[j], current[j + 1]);
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = a;
            if (current[j + 1] > 0.1) aliveCount++;
        }
    } else if (currentRule === 'conway' || currentRule === 'conway4') {
        aliveCount = 0;
        for (let i = 0, j = 0; i < data.length; i += 4, j++) {
            const [r, g, b, a] = PALETTE.conway(conwayGrid[j]);
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = a;
            if (conwayGrid[j]) aliveCount++;
        }
    } else { // wireworld
        aliveCount = 0;
        for (let i = 0, j = 0; i < data.length; i += 4, j++) {
            const [r, g, b, a] = PALETTE.wireworld(wireGrid[j]);
            data[i] = r; data[i+1] = g; data[i+2] = b; data[i+3] = a;
            if (wireGrid[j] >= 2) aliveCount++;
        }
    }
    ctx.putImageData(imageData, 0, 0);
}

// --- Main loop ---
function tick() {
    stepsPerFrame = parseInt(SPEED_SLIDER.value);
    if (currentRule === 'gray-scott') {
        feedRate = parseFloat(F_SLIDER.value);
        killRate = parseFloat(K_SLIDER.value);
        for (let s = 0; s < stepsPerFrame; s++) { grayScottStep(); stepCount++; }
    } else if (currentRule === 'conway' || currentRule === 'conway4') {
        for (let s = 0; s < stepsPerFrame; s++) { conwayStep(); stepCount++; }
    } else {
        for (let s = 0; s < stepsPerFrame; s++) { wireworldStep(); stepCount++; }
    }
    render();
    READOUT.textContent = `step ${stepCount} · ${aliveCount} alive · rule: ${currentRule}`;
    requestAnimationFrame(tick);
}

// --- Input ---
let drawing = false;
let drawValue = 1;

canvas.addEventListener('mousedown', (e) => {
    drawing = true;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / (rect.width / W));
    const y = Math.floor((e.clientY - rect.top) / (rect.height / H));
    if (currentRule === 'gray-scott') {
        current[idx(x, y)] = 0.5;
        current[idx(x, y) + 1] = 0.25;
    } else if (currentRule === 'conway' || currentRule === 'conway4') {
        conwayGrid[gridIdx(x, y)] = drawValue;
        drawValue = drawValue ? 0 : 1; // toggle
    } else {
        // Cycle through wireworld states when drawing
        const cur = wireGrid[gridIdx(x, y)];
        wireGrid[gridIdx(x, y)] = (cur + 1) % 4;
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (!drawing) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / (rect.width / W));
    const y = Math.floor((e.clientY - rect.top) / (rect.height / H));
    if (currentRule === 'gray-scott') {
        for (let dy = -2; dy <= 2; dy++) {
            for (let dx = -2; dx <= 2; dx++) {
                if (x + dx >= 0 && x + dx < W && y + dy >= 0 && y + dy < H) {
                    current[idx(x + dx, y + dy)] = 0.5;
                    current[idx(x + dx, y + dy) + 1] = 0.25;
    … (9018 chars)