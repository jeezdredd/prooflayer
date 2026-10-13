export type V3 = [number, number, number];

export interface Fiber {
  points: Float32Array;
  count: number;
  length: number;
  base: V3;
}

export interface BrainModel {
  positions: Float32Array;
  shade: Float32Array;
  seeds: Float32Array;
  fibers: Fiber[];
  members: V3[];
  memberFibers: number[];
  stemFiber: number;
  ambientFibers: number[];
  core: V3;
  verdict: V3;
}

export function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const PERM = (() => {
  const rand = mulberry32(7);
  const base = Array.from({ length: 256 }, (_, i) => i);
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [base[i], base[j]] = [base[j], base[i]];
  }
  const p = new Uint8Array(512);
  for (let i = 0; i < 512; i++) p[i] = base[i & 255];
  return p;
})();

const fade = (t: number) => t * t * t * (t * (t * 6 - 15) + 10);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

function grad(hash: number, x: number, y: number, z: number) {
  const h = hash & 15;
  const u = h < 8 ? x : y;
  const v = h < 4 ? y : h === 12 || h === 14 ? x : z;
  return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
}

export function perlin(x: number, y: number, z: number) {
  const X = Math.floor(x) & 255;
  const Y = Math.floor(y) & 255;
  const Z = Math.floor(z) & 255;
  x -= Math.floor(x);
  y -= Math.floor(y);
  z -= Math.floor(z);
  const u = fade(x);
  const v = fade(y);
  const w = fade(z);
  const A = PERM[X] + Y;
  const AA = PERM[A] + Z;
  const AB = PERM[A + 1] + Z;
  const B = PERM[X + 1] + Y;
  const BA = PERM[B] + Z;
  const BB = PERM[B + 1] + Z;
  return lerp(
    lerp(
      lerp(grad(PERM[AA], x, y, z), grad(PERM[BA], x - 1, y, z), u),
      lerp(grad(PERM[AB], x, y - 1, z), grad(PERM[BB], x - 1, y - 1, z), u),
      v,
    ),
    lerp(
      lerp(grad(PERM[AA + 1], x, y, z - 1), grad(PERM[BA + 1], x - 1, y, z - 1), u),
      lerp(grad(PERM[AB + 1], x, y - 1, z - 1), grad(PERM[BB + 1], x - 1, y - 1, z - 1), u),
      v,
    ),
    w,
  );
}

const smooth = (e0: number, e1: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

function ridge(x: number, y: number, z: number) {
  const f = 6.2;
  const wx = perlin(x * 2.1 + 3.1, y * 2.1, z * 2.1) * 0.9;
  const wy = perlin(x * 2.1, y * 2.1 + 7.7, z * 2.1) * 0.9;
  const wz = perlin(x * 2.1, y * 2.1, z * 2.1 + 1.9) * 0.9;
  const r = 1 - Math.abs(perlin(x * f + wx, y * f + wy, z * f + wz));
  return r ** 5;
}

function cerebrum(dx: number, dy: number, dz: number): { p: V3; shade: number } {
  const side = Math.sign(dx) || 1;
  let x = dx * 0.66 * (1 - 0.16 * dz * dz);
  let y = dy * 0.56;
  const z = dz * 0.86 * (1 - 0.05 * Math.max(0, dy));
  if (y < 0) y *= 0.62;
  const temporal = smooth(0.25, 0.75, Math.abs(dx)) * Math.exp(-(((dz - 0.08) / 0.34) ** 2)) * smooth(0.3, -0.35, dy);
  y -= 0.16 * temporal;
  x *= 1 + 0.05 * temporal;
  const midline = Math.exp(-((dx / 0.07) ** 2)) * smooth(-0.15, 0.3, dy);
  x += side * 0.022;
  y -= 0.07 * midline;
  const lateral = smooth(0.42, 0.8, Math.abs(dx));
  const sylvianY = -0.16 + (0.38 - dz) * 0.5;
  const sylvian = lateral * Math.exp(-(((dy - sylvianY) / 0.055) ** 2)) * smooth(-0.42, -0.2, dz) * smooth(0.48, 0.3, dz);
  const centralZ = 0.05 + (dy - 0.2) * 0.35;
  const central = smooth(-0.1, 0.35, dy) * Math.exp(-(((dz - centralZ) / 0.035) ** 2)) * 0.6;
  const r = ridge(x, y, z);
  const groove = Math.max(sylvian, midline * 0.9, central);
  const scale = 1 + 0.03 * r - 0.06 * groove;
  return { p: [x * scale, y * scale, z * scale], shade: (0.1 + 0.9 * r) * (1 - 0.9 * groove) };
}

function cerebellum(dx: number, dy: number, dz: number): { p: V3; shade: number } {
  const x = dx * 0.44;
  const y = dy * 0.2 - 0.37;
  const z = dz * 0.27 - 0.5;
  const folia = 0.5 + 0.5 * Math.sin(dy * 34 + perlin(dx * 3, dy * 3, dz * 3) * 2.4);
  const vermis = 1 - 0.6 * Math.exp(-((dx / 0.08) ** 2));
  return { p: [x, y, z], shade: (0.12 + 0.6 * folia ** 3) * vermis };
}

export function surfacePoint(dir: V3): V3 {
  const n = Math.hypot(dir[0], dir[1], dir[2]) || 1;
  return cerebrum(dir[0] / n, dir[1] / n, dir[2] / n).p;
}

function bezier(a: V3, c: V3, b: V3, segments: number): { points: Float32Array; length: number } {
  const points = new Float32Array((segments + 1) * 3);
  let length = 0;
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const k0 = (1 - t) * (1 - t);
    const k1 = 2 * (1 - t) * t;
    const k2 = t * t;
    points[i * 3] = k0 * a[0] + k1 * c[0] + k2 * b[0];
    points[i * 3 + 1] = k0 * a[1] + k1 * c[1] + k2 * b[1];
    points[i * 3 + 2] = k0 * a[2] + k1 * c[2] + k2 * b[2];
    if (i > 0) {
      length += Math.hypot(
        points[i * 3] - points[i * 3 - 3],
        points[i * 3 + 1] - points[i * 3 - 2],
        points[i * 3 + 2] - points[i * 3 - 1],
      );
    }
  }
  return { points, length };
}

export function buildBrain(memberDirs: V3[]): BrainModel {
  const rand = mulberry32(1987);
  const positions: number[] = [];
  const shade: number[] = [];
  const seeds: number[] = [];
  const unit = (): V3 => {
    const z = rand() * 2 - 1;
    const phi = rand() * Math.PI * 2;
    const r = Math.sqrt(1 - z * z);
    return [r * Math.cos(phi), z, r * Math.sin(phi)];
  };
  const push = (p: V3, s: number) => {
    positions.push(p[0], p[1], p[2]);
    shade.push(s);
    seeds.push(rand());
  };

  const surface: V3[] = [];
  for (let accepted = 0, tries = 0; accepted < 14000 && tries < 160000; tries++) {
    const [dx, dy, dz] = unit();
    const { p, shade: s } = cerebrum(dx, dy, dz);
    if (rand() > 0.06 + 0.94 * s ** 1.4) continue;
    push(p, s);
    if (accepted % 9 === 0) surface.push(p);
    accepted++;
  }
  for (let i = 0; i < 2600; i++) {
    const [dx, dy, dz] = unit();
    if (dy > 0.55 && dz > 0.2) continue;
    const { p, shade: s } = cerebellum(dx, dy, dz);
    push(p, s);
  }
  for (let i = 0; i < 900; i++) {
    const t = rand();
    const a = rand() * Math.PI * 2;
    const radius = (0.085 * (1 - 0.35 * t) + 0.035 * Math.exp(-(((t - 0.22) / 0.12) ** 2))) * (0.92 + rand() * 0.08);
    const cy = lerp(-0.22, -0.9, t);
    const cz = lerp(-0.2, -0.3, t);
    push([Math.cos(a) * radius, cy, cz + Math.sin(a) * radius * 0.9], 0.22 + 0.25 * rand());
  }
  for (let i = 0; i < 700; i++) {
    const [dx, dy, dz] = unit();
    const depth = 0.25 + rand() * 0.6;
    const { p } = cerebrum(dx, dy, dz);
    push([p[0] * depth, p[1] * depth, p[2] * depth], 0.08 + rand() * 0.12);
  }

  const core: V3 = [0, -0.07, -0.08];
  const verdict: V3 = [0, -1.08, -0.31];
  const fibers: Fiber[] = [];
  const addFiber = (a: V3, c: V3, b: V3, base: V3, segments: number) => {
    const { points, length } = bezier(a, c, b, segments);
    fibers.push({ points, count: segments + 1, length, base });
    return fibers.length - 1;
  };

  const ambientFibers: number[] = [];
  for (let i = 0; i < 190; i++) {
    const a = surface[Math.floor(rand() * surface.length)];
    let b = surface[Math.floor(rand() * surface.length)];
    for (let guard = 0; guard < 8 && Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) < 0.55; guard++) {
      b = surface[Math.floor(rand() * surface.length)];
    }
    const pull = 0.15 + rand() * 0.25;
    const c: V3 = [
      (a[0] + b[0]) * 0.5 * pull + core[0] * 0.3,
      (a[1] + b[1]) * 0.5 * pull + core[1] * 0.3 + 0.05,
      (a[2] + b[2]) * 0.5 * pull + core[2] * 0.3,
    ];
    const dx = Math.abs(a[0] - b[0]);
    const dy = Math.abs(a[1] - b[1]);
    const dz = Math.abs(a[2] - b[2]);
    const n = Math.hypot(dx, dy, dz) || 1;
    const base: V3 = [lerp(0.55, dx / n, 0.5), lerp(0.6, dy / n, 0.3), lerp(0.95, dz / n + 0.3, 0.5)];
    ambientFibers.push(addFiber(a, c, b, base, 36));
  }

  const members = memberDirs.map((d) => surfacePoint(d));
  const memberFibers = members.map((m) => {
    const c: V3 = [m[0] * 0.42 + core[0] * 0.5, m[1] * 0.42 + core[1] * 0.5 + 0.08, m[2] * 0.42 + core[2] * 0.5];
    return addFiber(m, c, core, [0.6, 0.65, 0.95], 44);
  });
  const stemFiber = addFiber(core, [0, -0.56, -0.18], verdict, [0.6, 0.65, 0.95], 44);

  return {
    positions: new Float32Array(positions),
    shade: new Float32Array(shade),
    seeds: new Float32Array(seeds),
    fibers,
    members,
    memberFibers,
    stemFiber,
    ambientFibers,
    core,
    verdict,
  };
}

export function pointOnFiber(f: Fiber, t: number, out: V3): V3 {
  const x = Math.min(1, Math.max(0, t)) * (f.count - 1);
  const i = Math.min(f.count - 2, Math.floor(x));
  const k = x - i;
  const p = f.points;
  out[0] = p[i * 3] + (p[i * 3 + 3] - p[i * 3]) * k;
  out[1] = p[i * 3 + 1] + (p[i * 3 + 4] - p[i * 3 + 1]) * k;
  out[2] = p[i * 3 + 2] + (p[i * 3 + 5] - p[i * 3 + 2]) * k;
  return out;
}
