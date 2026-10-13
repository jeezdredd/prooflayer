import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import * as THREE from "three";
import { buildBrain, mulberry32, pointOnFiber, type V3 } from "./brain/model";

export type MemberKind = "provenance" | "image" | "video" | "audio" | "text";

export interface BrainMember {
  code: string;
  short: string;
  name: string;
  tag: string;
  kind: MemberKind;
}

interface Props {
  members: BrainMember[];
  activeCode: string | null;
  onSelect: (code: string) => void;
  verdictLabel: string;
}

const KIND_RGB: Record<MemberKind, V3> = {
  provenance: [0.29, 0.87, 0.5],
  image: [0.96, 0.69, 0.26],
  video: [0.91, 0.47, 0.98],
  audio: [0.65, 0.55, 0.98],
  text: [0.13, 0.83, 0.93],
};
const KIND_HEX: Record<MemberKind, string> = {
  provenance: "#4ade80",
  image: "#f5b042",
  video: "#e879f9",
  audio: "#a78bfa",
  text: "#22d3ee",
};
const KIND_AREA: Record<MemberKind, string> = {
  provenance: "prefrontal · memory",
  image: "visual cortex",
  video: "motion area",
  audio: "auditory cortex",
  text: "language area",
};
const KIND_LABEL: Record<MemberKind, string> = {
  provenance: "Provenance",
  image: "Image",
  video: "Video",
  audio: "Audio",
  text: "Text",
};

const MEMBER_DIRS: V3[] = [
  [-0.38, 0.42, 0.82],
  [-0.36, 0.02, -0.93],
  [-0.3, 0.36, -0.88],
  [-0.48, 0.62, -0.62],
  [-0.62, -0.18, -0.76],
  [-0.2, 0.62, -0.76],
  [-0.68, -0.5, -0.4],
  [-0.86, 0.08, -0.48],
  [-0.92, -0.26, 0.08],
  [-0.8, 0.02, 0.52],
];

const CASES = [
  { id: "0507", file: "img_4232.png", verdict: "Synthetic", score: "0.87", rgb: [1, 0.34, 0.45] as V3, tone: "text-signal-blood" },
  { id: "0508", file: "DSC_1187.jpg", verdict: "Authentic", score: "0.12", rgb: [0.29, 0.87, 0.5] as V3, tone: "text-signal-sage" },
  { id: "0509", file: "press_still.webp", verdict: "Needs review", score: "split", rgb: [0.96, 0.69, 0.26] as V3, tone: "text-signal-amber" },
];

const FOV = 32;
const CENTER_Y = -0.24;
const TRAIL = 7;
const MAX_PULSES = 90;

const CORTEX_VERT = `
uniform float uTime;
uniform float uSize;
uniform float uCamDist;
uniform float uScan;
uniform vec3 uMember[MEMBERS];
uniform vec3 uMemberColor[MEMBERS];
uniform float uMemberHeat[MEMBERS];
attribute float aShade;
attribute float aSeed;
varying vec3 vColor;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float depth = -mv.z;
  float twinkle = 0.84 + 0.16 * sin(uTime * (0.5 + aSeed * 1.6) + aSeed * 40.0);
  vec3 base = vec3(0.58, 0.64, 1.0) * (0.022 + 0.34 * pow(aShade, 1.25)) * twinkle;
  vec3 tint = vec3(0.0);
  for (int i = 0; i < MEMBERS; i++) {
    float d = distance(position, uMember[i]);
    tint += uMemberColor[i] * uMemberHeat[i] * exp(-d * d / 0.02);
  }
  float scanD = (position.y - uScan) / 0.035;
  float scan = exp(-scanD * scanD) * (0.25 + aShade);
  float fade = clamp(1.2 - (depth - uCamDist) * 1.15, 0.12, 1.0);
  vColor = (base + tint * 0.55 + vec3(0.13, 0.83, 0.93) * scan * 0.22) * fade;
  gl_PointSize = (0.0085 + 0.004 * aShade + scan * 0.006) * uSize / depth;
  gl_Position = projectionMatrix * mv;
}`;

const CORTEX_FRAG = `
varying vec3 vColor;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = dot(c, c) * 4.0;
  if (d > 1.0) discard;
  vec3 col = vColor * pow(1.0 - d, 1.5);
  gl_FragColor = vec4(col, max(col.r, max(col.g, col.b)));
}`;

const LINE_VERT = `
uniform float uCamDist;
attribute vec3 aColor;
varying vec3 vColor;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vColor = aColor * clamp(1.25 - (-mv.z - uCamDist) * 1.0, 0.2, 1.0);
  gl_Position = projectionMatrix * mv;
}`;

const LINE_FRAG = `
varying vec3 vColor;
void main() {
  gl_FragColor = vec4(vColor, max(vColor.r, max(vColor.g, vColor.b)));
}`;

const GLOW_VERT = `
uniform float uSize;
uniform float uCamDist;
attribute vec3 aColor;
attribute float aSize;
attribute float aAlpha;
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float depth = -mv.z;
  vColor = aColor;
  vAlpha = aAlpha * clamp(1.3 - (depth - uCamDist) * 0.9, 0.3, 1.0);
  gl_PointSize = aSize * uSize / depth;
  gl_Position = projectionMatrix * mv;
}`;

const GLOW_FRAG = `
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = dot(c, c) * 4.0;
  if (d > 1.0) discard;
  float halo = exp(-d * 5.0) * (1.0 - d);
  float hot = exp(-d * 70.0);
  vec3 col = (vColor * halo * 0.8 + vec3(1.0) * hot * 0.9) * vAlpha;
  gl_FragColor = vec4(col, max(col.r, max(col.g, col.b)));
}`;

function lightMaterial(vertexShader: string, fragmentShader: string, uniforms: Record<string, THREE.IUniform>, defines?: Record<string, number>) {
  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms,
    defines,
    transparent: true,
    depthTest: false,
    depthWrite: false,
    blending: THREE.CustomBlending,
    blendEquation: THREE.AddEquation,
    blendSrc: THREE.OneFactor,
    blendDst: THREE.OneFactor,
  });
}

function haloGeometry(seed: number) {
  const rand = mulberry32(seed);
  const pos: number[] = [];
  const shade: number[] = [];
  const seeds: number[] = [];
  const rings: [number, number, number][] = [
    [1.08, 0.1, 0.0],
    [1.22, -0.45, 1.1],
  ];
  for (const [radius, tilt, phase] of rings) {
    for (let i = 0; i < 900; i++) {
      const a = (i / 900) * Math.PI * 2;
      if (Math.sin(a * 36 + phase) > 0.35) continue;
      const x = Math.cos(a) * radius;
      const z = Math.sin(a) * radius * 0.82;
      pos.push(x, -0.12 + z * Math.sin(tilt) * 0.3, z * Math.cos(tilt));
      shade.push(0.35 + rand() * 0.25);
      seeds.push(rand());
    }
  }
  for (let i = 0; i < 420; i++) {
    const r = 0.9 + rand() * 0.75;
    const t = rand() * Math.PI * 2;
    const u = rand() * 2 - 1;
    const s = Math.sqrt(1 - u * u);
    pos.push(Math.cos(t) * s * r, u * r * 0.8 - 0.25, Math.sin(t) * s * r);
    shade.push(0.1 + rand() * 0.35);
    seeds.push(rand());
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pos), 3));
  geo.setAttribute("aShade", new THREE.BufferAttribute(new Float32Array(shade), 1));
  geo.setAttribute("aSeed", new THREE.BufferAttribute(new Float32Array(seeds), 1));
  return geo;
}

interface Pulse {
  fiber: number;
  t: number;
  speed: number;
  color: V3;
  strength: number;
  reverse: boolean;
  arrive?: () => void;
}

export default function TribunalBrain({ members, activeCode, onSelect, verdictLabel }: Props) {
  const wrapRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const glRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const verdictRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const calloutRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const focusRef = useRef<number | null>(null);
  const redrawRef = useRef<(() => void) | null>(null);
  const reduceMotion = useReducedMotion();
  const [hovered, setHovered] = useState<number | null>(null);
  const [caseIdx, setCaseIdx] = useState(0);
  const [ruled, setRuled] = useState(false);
  const [failed, setFailed] = useState(false);

  const dirs = useMemo(
    () =>
      members.map((_, i): V3 => {
        if (i < MEMBER_DIRS.length) return MEMBER_DIRS[i];
        const a = i * 2.399;
        return [-0.7, Math.sin(a) * 0.5, Math.cos(a) * 0.7];
      }),
    [members],
  );
  const model = useMemo(() => buildBrain(dirs), [dirs]);
  const columns = useMemo(() => {
    const order = members.map((_, i) => i).sort((a, b) => model.members[b][1] - model.members[a][1]);
    return {
      back: order.filter((i) => model.members[i][2] <= -0.3),
      front: order.filter((i) => model.members[i][2] > -0.3),
    };
  }, [members, model]);
  const kinds = useMemo(() => Array.from(new Set(members.map((m) => m.kind))), [members]);

  const activeIndex = activeCode ? members.findIndex((m) => m.code === activeCode) : -1;
  const focusIndex = hovered ?? (activeIndex >= 0 ? activeIndex : null);
  focusRef.current = focusIndex;

  useEffect(() => {
    const canvas = glRef.current;
    const stage = stageRef.current;
    const wrap = wrapRef.current;
    const overlay = overlayRef.current;
    if (!canvas || !stage || !wrap || !overlay) return;
    const octx = overlay.getContext("2d");

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch {
      setFailed(true);
      return;
    }
    renderer.setClearColor(0x000000, 0);

    const n = members.length;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 20);
    const group = new THREE.Group();
    scene.add(group);

    const memberHeat = new Array(n).fill(0);
    const cortexUniforms = {
      uTime: { value: 0 },
      uSize: { value: 1000 },
      uCamDist: { value: 4 },
      uScan: { value: 0 },
      uMember: { value: model.members.map((m) => new THREE.Vector3(...m)) },
      uMemberColor: { value: members.map((m) => new THREE.Vector3(...KIND_RGB[m.kind])) },
      uMemberHeat: { value: memberHeat },
    };
    const cortexGeo = new THREE.BufferGeometry();
    cortexGeo.setAttribute("position", new THREE.BufferAttribute(model.positions, 3));
    cortexGeo.setAttribute("aShade", new THREE.BufferAttribute(model.shade, 1));
    cortexGeo.setAttribute("aSeed", new THREE.BufferAttribute(model.seeds, 1));
    const cortexMat = lightMaterial(CORTEX_VERT, CORTEX_FRAG, cortexUniforms, { MEMBERS: Math.max(1, n) });
    group.add(new THREE.Points(cortexGeo, cortexMat));

    const haloGeo = haloGeometry(77);
    const halo = new THREE.Points(haloGeo, cortexMat);
    halo.frustumCulled = false;
    scene.add(halo);

    const fiberOffset: number[] = [];
    let vertexCount = 0;
    for (const f of model.fibers) {
      fiberOffset.push(vertexCount);
      vertexCount += (f.count - 1) * 2;
    }
    const linePos = new Float32Array(vertexCount * 3);
    const lineT = new Float32Array(vertexCount);
    const baseColor = new Float32Array(vertexCount * 3);
    const memberOfFiber = new Map<number, number>();
    model.memberFibers.forEach((f, i) => memberOfFiber.set(f, i));
    model.fibers.forEach((f, fi) => {
      const member = memberOfFiber.get(fi);
      const isStem = fi === model.stemFiber;
      const intensity = member !== undefined ? 0.08 : isStem ? 0.1 : 0.05;
      const tint: V3 = member !== undefined ? KIND_RGB[members[member].kind] : f.base;
      for (let s = 0; s < f.count - 1; s++) {
        for (let k = 0; k < 2; k++) {
          const v = fiberOffset[fi] + s * 2 + k;
          const p = s + k;
          linePos[v * 3] = f.points[p * 3];
          linePos[v * 3 + 1] = f.points[p * 3 + 1];
          linePos[v * 3 + 2] = f.points[p * 3 + 2];
          lineT[v] = p / (f.count - 1);
          const taper = 0.55 + 0.45 * Math.sin(Math.PI * lineT[v]);
          baseColor[v * 3] = tint[0] * intensity * taper;
          baseColor[v * 3 + 1] = tint[1] * intensity * taper;
          baseColor[v * 3 + 2] = tint[2] * intensity * taper;
        }
      }
    });
    const lineColor = new Float32Array(baseColor);
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
    const lineColorAttr = new THREE.BufferAttribute(lineColor, 3).setUsage(THREE.DynamicDrawUsage);
    lineGeo.setAttribute("aColor", lineColorAttr);
    const lineUniforms = { uCamDist: { value: 4 } };
    const lineMat = lightMaterial(LINE_VERT, LINE_FRAG, lineUniforms);
    group.add(new THREE.LineSegments(lineGeo, lineMat));

    const glowCap = n + 2 + MAX_PULSES * (TRAIL + 1);
    const glowPos = new Float32Array(glowCap * 3);
    const glowColor = new Float32Array(glowCap * 3);
    const glowSize = new Float32Array(glowCap);
    const glowAlpha = new Float32Array(glowCap);
    const glowGeo = new THREE.BufferGeometry();
    const glowAttrs = [
      new THREE.BufferAttribute(glowPos, 3).setUsage(THREE.DynamicDrawUsage),
      new THREE.BufferAttribute(glowColor, 3).setUsage(THREE.DynamicDrawUsage),
      new THREE.BufferAttribute(glowSize, 1).setUsage(THREE.DynamicDrawUsage),
      new THREE.BufferAttribute(glowAlpha, 1).setUsage(THREE.DynamicDrawUsage),
    ];
    glowGeo.setAttribute("position", glowAttrs[0]);
    glowGeo.setAttribute("aColor", glowAttrs[1]);
    glowGeo.setAttribute("aSize", glowAttrs[2]);
    glowGeo.setAttribute("aAlpha", glowAttrs[3]);
    const glowUniforms = { uSize: { value: 1000 }, uCamDist: { value: 4 } };
    const glowMat = lightMaterial(GLOW_VERT, GLOW_FRAG, glowUniforms);
    const glowPoints = new THREE.Points(glowGeo, glowMat);
    glowPoints.frustumCulled = false;
    group.add(glowPoints);

    let stageW = 1;
    let stageH = 1;
    let stageX = 0;
    let stageY = 0;
    let anchors: ({ x: number; y: number; dir: number } | null)[] = [];
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      stageW = Math.max(1, stage.clientWidth);
      stageH = Math.max(1, stage.clientHeight);
      renderer.setPixelRatio(dpr);
      renderer.setSize(stageW, stageH, false);
      const aspect = stageW / stageH;
      camera.aspect = aspect;
      const tan = Math.tan((FOV * Math.PI) / 360);
      const dist = Math.max(1.02 / tan, 1.0 / (tan * aspect));
      camera.position.set(0, CENTER_Y, dist);
      camera.lookAt(0, CENTER_Y, 0);
      camera.updateProjectionMatrix();
      const pxSize = (stageH * dpr) / (2 * tan);
      cortexUniforms.uSize.value = pxSize;
      glowUniforms.uSize.value = pxSize;
      cortexUniforms.uCamDist.value = dist;
      lineUniforms.uCamDist.value = dist;
      glowUniforms.uCamDist.value = dist;
      const wrapRect = wrap.getBoundingClientRect();
      const stageRect = stage.getBoundingClientRect();
      stageX = stageRect.left - wrapRect.left;
      stageY = stageRect.top - wrapRect.top;
      overlay.width = Math.round(wrapRect.width * dpr);
      overlay.height = Math.round(wrapRect.height * dpr);
      octx?.setTransform(dpr, 0, 0, dpr, 0, 0);
      anchors = members.map((_, i) => {
        const el = calloutRefs.current[i];
        if (!el || el.offsetParent === null) return null;
        const r = el.getBoundingClientRect();
        const left = r.left + r.width / 2 < stageRect.left + stageRect.width / 2;
        return { x: (left ? r.right : r.left) - wrapRect.left, y: r.top + 9 - wrapRect.top, dir: left ? 1 : -1 };
      });
    };

    const rand = mulberry32(42);
    const pulses: Pulse[] = [];
    let coreHeat = 0;
    let verdictHeat = 0;
    let verdictRgb: V3 = [1, 1, 1];
    let ambientTimer = 0.3;
    let focusTimer = 0;
    let caseNo = 0;
    let schedule: number[] = [];
    let fired: boolean[] = [];
    let caseClock = 0;
    let pending = 0;
    let holdTimer = -1;

    const fire = (fiber: number, color: V3, strength: number, worldSpeed: number, reverse: boolean, arrive?: () => void) => {
      if (pulses.length >= MAX_PULSES) {
        const dropped = pulses.findIndex((p) => !p.arrive);
        pulses.splice(dropped >= 0 ? dropped : 0, 1);
      }
      pulses.push({ fiber, t: 0, speed: worldSpeed / model.fibers[fiber].length, color, strength, reverse, arrive });
    };
    const fireMember = (i: number, strength: number, arrive?: () => void) => {
      memberHeat[i] = Math.min(1, memberHeat[i] + strength);
      fire(model.memberFibers[i], KIND_RGB[members[i].kind], strength, 0.8 + rand() * 0.2, false, arrive);
    };
    const startCase = (idx: number) => {
      caseNo = idx;
      caseClock = 0;
      holdTimer = -1;
      pending = n;
      const order = members.map((_, i) => i).sort(() => rand() - 0.5);
      schedule = new Array(n).fill(0);
      order.forEach((m, rank) => (schedule[m] = 0.5 + rank * 0.26 + rand() * 0.12));
      fired = new Array(n).fill(false);
      setCaseIdx(idx);
      setRuled(false);
    };
    const onVote = () => {
      coreHeat = Math.min(1.4, coreHeat + 0.22);
      pending -= 1;
      if (pending > 0) return;
      const c = CASES[caseNo];
      fire(model.stemFiber, c.rgb, 1.2, 0.7, false, () => {
        verdictHeat = 1;
        verdictRgb = c.rgb;
        holdTimer = 3.4;
        setRuled(true);
      });
    };

    const tmp: V3 = [0, 0, 0];
    const step = (dt: number) => {
      const decay = Math.exp(-dt * 1.8);
      for (let i = 0; i < n; i++) memberHeat[i] *= decay;
      coreHeat *= Math.exp(-dt * 1.2);
      verdictHeat *= Math.exp(-dt * 0.35);

      caseClock += dt;
      for (let i = 0; i < n; i++) {
        if (!fired[i] && caseClock >= schedule[i]) {
          fired[i] = true;
          fireMember(i, 0.9, onVote);
        }
      }
      if (holdTimer > 0) {
        holdTimer -= dt;
        if (holdTimer <= 0) startCase((caseNo + 1) % CASES.length);
      }

      const focus = focusRef.current;
      if (focus !== null && focus < n) {
        focusTimer -= dt;
        if (focusTimer <= 0) {
          fireMember(focus, 1);
          focusTimer = 1.1;
        }
      } else {
        focusTimer = 0;
      }

      ambientTimer -= dt;
      if (ambientTimer <= 0) {
        const f = model.ambientFibers[Math.floor(rand() * model.ambientFibers.length)];
        const b = model.fibers[f].base;
        fire(f, [b[0] * 0.8, b[1] * 0.8, b[2] * 0.9], 0.38 + rand() * 0.25, 0.45 + rand() * 0.3, rand() < 0.5);
        ambientTimer = 0.07 + rand() * 0.16;
      }

      for (let i = pulses.length - 1; i >= 0; i--) {
        const p = pulses[i];
        p.t += p.speed * dt;
        if (p.t >= 1) {
          pulses.splice(i, 1);
          p.arrive?.();
        }
      }
    };

    const memberWorld = new THREE.Vector3();
    const project = new THREE.Vector3();
    const render = (time: number, px: number, py: number) => {
      const yaw = Math.PI / 2 + 0.42 * Math.sin(time * 0.15) + px;
      const pitch = 0.2 + 0.05 * Math.sin(time * 0.11 + 1.3) + py;
      group.rotation.set(pitch, yaw, 0);
      group.updateMatrixWorld();
      halo.rotation.set(pitch * 0.6, time * 0.06 + px * 0.5, 0.08);
      cortexUniforms.uTime.value = time;
      cortexUniforms.uScan.value = -0.95 + (0.5 - 0.5 * Math.cos(time * 0.32)) * 1.6;

      const focus = focusRef.current;
      lineColor.set(baseColor);
      const lightFiber = (fi: number, color: V3, amount: (t: number) => number) => {
        const f = model.fibers[fi];
        const start = fiberOffset[fi];
        const end = start + (f.count - 1) * 2;
        for (let v = start; v < end; v++) {
          const a = amount(lineT[v]);
          if (a <= 0.002) continue;
          lineColor[v * 3] += color[0] * a;
          lineColor[v * 3 + 1] += color[1] * a;
          lineColor[v * 3 + 2] += color[2] * a;
        }
      };
      if (focus !== null && focus < n) lightFiber(model.memberFibers[focus], KIND_RGB[members[focus].kind], () => 0.22);
      if (focus !== null) lightFiber(model.stemFiber, [0.6, 0.65, 0.95], () => 0.1);

      let g = 0;
      const glow = (p: V3, c: V3, size: number, alpha: number) => {
        glowPos[g * 3] = p[0];
        glowPos[g * 3 + 1] = p[1];
        glowPos[g * 3 + 2] = p[2];
        glowColor[g * 3] = c[0];
        glowColor[g * 3 + 1] = c[1];
        glowColor[g * 3 + 2] = c[2];
        glowSize[g] = size;
        glowAlpha[g] = alpha;
        g++;
      };

      for (const p of pulses) {
        const head = p.reverse ? 1 - p.t : p.t;
        lightFiber(p.fiber, p.color, (t) => {
          const behind = p.reverse ? t - head : head - t;
          if (behind < -0.02) return 0;
          return p.strength * 0.55 * Math.exp(-Math.max(0, behind) * 7);
        });
        const f = model.fibers[p.fiber];
        for (let k = TRAIL; k >= 1; k--) {
          const tt = p.reverse ? head + k * 0.018 : head - k * 0.018;
          if (tt < 0 || tt > 1) continue;
          pointOnFiber(f, tt, tmp);
          glow(tmp, p.color, 0.022 * (1 - k / (TRAIL + 1)) * (0.6 + p.strength * 0.5), (1 - k / (TRAIL + 1)) * 0.6 * p.strength);
        }
        pointOnFiber(f, head, tmp);
        glow(tmp, p.color, 0.05 + 0.04 * p.strength, Math.min(1, 0.35 + p.strength * 0.6));
      }
      lineColorAttr.needsUpdate = true;

      members.forEach((m, i) => {
        const h = Math.max(memberHeat[i], focus === i ? 0.75 : 0);
        glow(model.members[i], KIND_RGB[m.kind], 0.07 + h * 0.09, 0.55 + h * 0.45);
      });
      glow(model.core, [0.13, 0.83, 0.93], 0.16 + coreHeat * 0.14, 0.45 + Math.min(1, coreHeat) * 0.55);
      glow(model.verdict, verdictRgb, 0.12 + verdictHeat * 0.16, 0.4 + verdictHeat * 0.6);
      glowGeo.setDrawRange(0, g);
      for (const a of glowAttrs) a.needsUpdate = true;
      for (let i = 0; i < n; i++) cortexUniforms.uMemberHeat.value[i] = Math.max(memberHeat[i], focus === i ? 0.6 : 0);

      renderer.render(scene, camera);

      if (octx) octx.clearRect(0, 0, overlay.width, overlay.height);
      members.forEach((m, i) => {
        memberWorld.set(...model.members[i]).applyMatrix4(group.matrixWorld);
        const facing = memberWorld.z > -0.15;
        project.copy(memberWorld).project(camera);
        const x = ((project.x + 1) / 2) * stageW;
        const y = ((1 - project.y) / 2) * stageH;
        const node = nodeRefs.current[i];
        if (node) {
          node.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
          node.style.opacity = facing || focus === i ? "1" : "0.45";
        }
        const anchor = anchors[i];
        if (!octx || !anchor) return;
        const nx = stageX + x;
        const ny = stageY + y;
        const lit = Math.max(memberHeat[i] * 0.6, focus === i ? 0.9 : 0);
        const c = KIND_RGB[m.kind];
        octx.strokeStyle = lit > 0.05
          ? `rgba(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)},${0.18 + lit * 0.6})`
          : `rgba(255,255,255,${facing ? 0.13 : 0.07})`;
        octx.lineWidth = 1;
        octx.beginPath();
        octx.moveTo(anchor.x + anchor.dir * 6, anchor.y);
        octx.lineTo(anchor.x + anchor.dir * 22, anchor.y);
        octx.lineTo(nx, ny);
        octx.stroke();
      });
      memberWorld.set(...model.verdict).applyMatrix4(group.matrixWorld);
      project.copy(memberWorld).project(camera);
      if (verdictRef.current) {
        const vx = ((project.x + 1) / 2) * stageW;
        const vy = ((1 - project.y) / 2) * stageH;
        verdictRef.current.style.transform = `translate(${vx}px, ${vy + 18}px) translateX(-50%)`;
      }
    };

    resize();
    const ro = new ResizeObserver(() => {
      resize();
      if (reduceMotion) render(0, 0, 0);
    });
    ro.observe(wrap);

    let visible = true;
    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    io.observe(wrap);

    let targetX = 0;
    let targetY = 0;
    let px = 0;
    let py = 0;
    const onPointer = (e: PointerEvent) => {
      const r = wrap.getBoundingClientRect();
      targetX = ((e.clientX - r.left) / r.width - 0.5) * 0.22;
      targetY = ((e.clientY - r.top) / r.height - 0.5) * 0.12;
    };
    const onLeave = () => {
      targetX = 0;
      targetY = 0;
    };
    wrap.addEventListener("pointermove", onPointer);
    wrap.addEventListener("pointerleave", onLeave);

    let raf = 0;
    let last = performance.now();
    let clock = 0;
    let running = true;
    const loop = (now: number) => {
      if (!running) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (visible && !document.hidden) {
        clock += dt;
        const ease = 1 - Math.exp(-dt * 3);
        px += (targetX - px) * ease;
        py += (targetY - py) * ease;
        step(dt);
        render(clock, px, py);
      }
      raf = requestAnimationFrame(loop);
    };

    if (reduceMotion) {
      verdictHeat = 0.8;
      verdictRgb = CASES[0].rgb;
      setRuled(true);
      redrawRef.current = () => render(0, 0, 0);
      render(0, 0, 0);
    } else {
      startCase(0);
      raf = requestAnimationFrame(loop);
    }

    return () => {
      running = false;
      redrawRef.current = null;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      wrap.removeEventListener("pointermove", onPointer);
      wrap.removeEventListener("pointerleave", onLeave);
      cortexGeo.dispose();
      haloGeo.dispose();
      cortexMat.dispose();
      lineGeo.dispose();
      lineMat.dispose();
      glowGeo.dispose();
      glowMat.dispose();
      renderer.dispose();
    };
  }, [model, members, reduceMotion]);

  useEffect(() => {
    redrawRef.current?.();
  }, [focusIndex]);

  const focusMember = focusIndex !== null ? members[focusIndex] : null;
  const current = CASES[caseIdx];

  const callout = (i: number, side: "back" | "front") => {
    const m = members[i];
    const on = focusIndex === i;
    return (
      <li key={m.code}>
        <button
          ref={(el) => {
            calloutRefs.current[i] = el;
          }}
          type="button"
          aria-pressed={activeCode === m.code}
          onMouseEnter={() => setHovered(i)}
          onMouseLeave={() => setHovered(null)}
          onFocus={() => setHovered(i)}
          onBlur={() => setHovered(null)}
          onClick={() => onSelect(m.code)}
          className={`group block w-full py-1.5 focus:outline-none ${side === "back" ? "text-right" : "text-left"}`}
        >
          <span className="block font-mono text-[10px] uppercase tracking-[0.14em] leading-[18px]">
            {side === "front" && <span className="inline-block w-1.5 h-1.5 rounded-full mr-2 align-middle" style={{ background: KIND_HEX[m.kind] }} />}
            <span className="text-ink-600 tabular-nums mr-1.5">{m.code}</span>
            <span className={`transition-colors duration-300 ${on ? "text-ink-50" : "text-ink-300 group-hover:text-ink-100"}`}>{m.short}</span>
            {side === "back" && <span className="inline-block w-1.5 h-1.5 rounded-full ml-2 align-middle" style={{ background: KIND_HEX[m.kind] }} />}
          </span>
          <span className="block font-mono text-[9px] uppercase tracking-[0.16em] text-ink-600">{KIND_AREA[m.kind]}</span>
        </button>
      </li>
    );
  };

  return (
    <figure ref={wrapRef} className="relative case-card crop-marks px-4 sm:px-6 pt-4 pb-4 select-none">
      <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 w-full h-full" aria-hidden="true" />
      <figcaption className="relative flex items-center justify-between gap-4 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
        <span>
          Fig. 03 <span className="text-ink-700 mx-1.5">/</span> {verdictLabel}
          <span className="hidden sm:inline text-ink-700 mx-1.5">/</span>
          <span className="hidden sm:inline">left lateral view</span>
        </span>
        <span className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-signal-sage pulse-dot" />
          in session
        </span>
      </figcaption>

      <div className="relative grid md:grid-cols-[minmax(0,1fr)_minmax(0,2.6fr)_minmax(0,1fr)] gap-2 mt-2">
        <ol className="hidden md:flex flex-col justify-center gap-3 pr-2">{columns.back.map((i) => callout(i, "back"))}</ol>

        <div ref={stageRef} className="relative aspect-[20/23] md:aspect-[5/4] w-full overflow-hidden">
          <canvas ref={glRef} className="absolute inset-0 w-full h-full" aria-hidden="true" />
          {failed && (
            <div className="absolute inset-0 grid place-items-center font-mono text-[10px] uppercase tracking-[0.16em] text-ink-600">
              3D view unavailable on this device
            </div>
          )}
          {members.map((m, i) => (
            <button
              key={m.code}
              ref={(el) => {
                nodeRefs.current[i] = el;
              }}
              type="button"
              aria-label={`${m.name}: ${m.tag}`}
              aria-pressed={activeCode === m.code}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(i)}
              onBlur={() => setHovered(null)}
              onClick={() => onSelect(m.code)}
              className="absolute left-0 top-0 w-8 h-8 rounded-full transition-opacity duration-500 focus:outline-none focus-visible:ring-1 focus-visible:ring-signal-amber/70"
            >
              <span className="md:hidden pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-0.5 font-mono text-[9px] tabular-nums text-ink-400">
                {m.code}
              </span>
            </button>
          ))}
          <div ref={verdictRef} className="pointer-events-none absolute left-0 top-0 text-center whitespace-nowrap">
            <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-ink-500">Verdict</div>
            <AnimatePresence mode="wait">
              <motion.div
                key={ruled ? current.id : "pending"}
                initial={{ opacity: 0, y: 4, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={{ opacity: 0, y: -4, filter: "blur(4px)" }}
                transition={{ duration: 0.35 }}
                className={`font-display text-lg leading-tight mt-0.5 ${ruled ? current.tone : "text-ink-600 italic"}`}
              >
                {ruled ? current.verdict : "deliberating"}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        <ol className="hidden md:flex flex-col justify-center gap-3 pl-2">{columns.front.map((i) => callout(i, "front"))}</ol>
      </div>

      <div className="relative mt-3 pt-3 border-t border-[var(--line)] flex flex-wrap items-start justify-between gap-x-8 gap-y-3 min-h-[3.25rem]">
        <ul className="flex flex-wrap gap-x-4 gap-y-1.5 font-mono text-[9px] uppercase tracking-[0.16em] text-ink-500">
          {kinds.map((k) => (
            <li key={k} className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: KIND_HEX[k] }} />
              {KIND_LABEL[k]}
            </li>
          ))}
        </ul>
        <div className="text-right max-w-full sm:max-w-[60%]" aria-live="polite">
          <AnimatePresence mode="wait">
            {focusMember ? (
              <motion.div key={`m-${focusMember.code}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                <div className="font-display text-lg text-ink-50 leading-tight">{focusMember.name}</div>
                <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 mt-0.5">
                  {focusMember.tag} <span className="text-ink-700 mx-1">/</span> {KIND_AREA[focusMember.kind]}
                </div>
              </motion.div>
            ) : (
              <motion.div key={`c-${current.id}-${ruled}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }} className="font-mono text-[10px] uppercase tracking-[0.14em]">
                <div className="text-ink-500 ticker">
                  Case/2026-{current.id} <span className="text-ink-700 mx-1">·</span> {current.file}
                </div>
                <div className="mt-1">
                  {ruled ? (
                    <>
                      <span className={current.tone}>{current.verdict}</span>
                      <span className="text-ink-600 ml-2 tabular-nums">{current.score}</span>
                      {current.score === "split" && <span className="text-ink-500 ml-2">→ sent to a human reviewer</span>}
                    </>
                  ) : (
                    <span className="text-ink-400">{members.length} judges voting</span>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </figure>
  );
}
