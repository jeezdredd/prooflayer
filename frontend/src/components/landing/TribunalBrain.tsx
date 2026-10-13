import { useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

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

type RGB = [number, number, number];

const W = 1000;
const H = 680;

const KIND_COLOR: Record<MemberKind, RGB> = {
  provenance: [74, 222, 128],
  image: [245, 176, 66],
  video: [232, 121, 249],
  audio: [167, 139, 250],
  text: [34, 211, 238],
};
const CORE_COLOR: RGB = [34, 211, 238];
const VERDICT_COLOR: RGB = [245, 176, 66];
const AMBIENT_COLOR: RGB = [200, 210, 255];

const OUTLINE: [number, number][] = [
  [150, 330], [120, 240], [165, 150], [260, 80], [390, 40], [530, 32], [670, 55], [790, 115],
  [870, 210], [885, 300], [850, 370], [800, 405], [830, 440], [815, 500], [740, 525], [660, 505],
  [612, 478], [602, 540], [598, 598], [548, 598], [545, 520], [530, 470], [450, 455], [350, 450],
  [250, 425], [185, 385],
];

const MEMBER_SPOTS: [number, number][] = [
  [185, 250], [255, 145], [375, 88], [515, 72], [655, 96], [770, 172], [830, 290], [300, 388],
  [440, 410], [745, 372],
];

const CORE: [number, number] = [520, 300];
const STEM: [number, number][] = [[556, 395], [570, 470], [573, 535]];
const VERDICT: [number, number] = [573, 592];

interface Node {
  x: number;
  y: number;
  kind: "inter" | "member" | "core" | "stem" | "verdict";
  heat: number;
}

interface Edge {
  a: number;
  b: number;
  heat: number;
  color: RGB;
}

interface Impulse {
  path: number[];
  lengths: number[];
  total: number;
  d: number;
  speed: number;
  color: RGB;
  strength: number;
  toCore: boolean;
  lastSeg: number;
}

interface Graph {
  nodes: Node[];
  edges: Edge[];
  adj: Map<number, { to: number; edge: number }[]>;
  coreIdx: number;
  verdictIdx: number;
  stemPath: number[];
  memberIdx: number[];
  memberPaths: number[][];
  outline: Path2D;
  fissure: Path2D;
}

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function smoothClosedPath(points: [number, number][]): Path2D {
  const path = new Path2D();
  const n = points.length;
  path.moveTo(points[0][0], points[0][1]);
  for (let i = 0; i < n; i++) {
    const p0 = points[(i - 1 + n) % n];
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];
    path.bezierCurveTo(
      p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
      p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6,
      p2[0], p2[1],
    );
  }
  path.closePath();
  return path;
}

function dist(a: { x: number; y: number }, b: { x: number; y: number }) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function buildGraph(memberCount: number): Graph {
  const outline = smoothClosedPath(OUTLINE);
  const fissure = new Path2D();
  fissure.moveTo(235, 372);
  fissure.bezierCurveTo(330, 330, 470, 350, 640, 292);
  fissure.moveTo(690, 120);
  fissure.bezierCurveTo(640, 190, 660, 240, 620, 300);
  fissure.moveTo(410, 60);
  fissure.bezierCurveTo(430, 130, 400, 190, 430, 250);

  const probe = document.createElement("canvas").getContext("2d");
  const inside = (x: number, y: number) => (probe ? probe.isPointInPath(outline, x, y) : true);

  const nodes: Node[] = [];
  const memberIdx: number[] = [];
  for (let i = 0; i < memberCount; i++) {
    const [x, y] = MEMBER_SPOTS[i % MEMBER_SPOTS.length];
    memberIdx.push(nodes.length);
    nodes.push({ x, y, kind: "member", heat: 0 });
  }
  const coreIdx = nodes.length;
  nodes.push({ x: CORE[0], y: CORE[1], kind: "core", heat: 0 });
  const stemIdx = STEM.map(([x, y]) => {
    nodes.push({ x, y, kind: "stem", heat: 0 });
    return nodes.length - 1;
  });
  const verdictIdx = nodes.length;
  nodes.push({ x: VERDICT[0], y: VERDICT[1], kind: "verdict", heat: 0 });

  const rand = mulberry32(239);
  let inter = 0;
  for (let guard = 0; inter < 92 && guard < 20000; guard++) {
    const x = 120 + rand() * 770;
    const y = 30 + rand() * 500;
    if (!inside(x, y)) continue;
    if (y > 455 && x > 520 && x < 620) continue;
    if (nodes.some((n) => dist(n, { x, y }) < (n.kind === "inter" ? 40 : 52))) continue;
    nodes.push({ x, y, kind: "inter", heat: 0 });
    inter++;
  }

  const edgeKey = new Set<string>();
  const edges: Edge[] = [];
  const addEdge = (a: number, b: number) => {
    if (a === b) return;
    const key = a < b ? `${a}-${b}` : `${b}-${a}`;
    if (edgeKey.has(key)) return;
    edgeKey.add(key);
    edges.push({ a, b, heat: 0, color: AMBIENT_COLOR });
  };

  const brain = nodes.map((n, i) => ({ n, i })).filter(({ n }) => n.kind === "inter" || n.kind === "member" || n.kind === "core");
  for (const { n, i } of brain) {
    brain
      .filter(({ i: j }) => j !== i)
      .map(({ n: m, i: j }) => ({ j, d: dist(n, m) }))
      .filter(({ d }) => d < 150)
      .sort((p, q) => p.d - q.d)
      .slice(0, n.kind === "inter" ? 3 : 4)
      .forEach(({ j }) => addEdge(i, j));
  }

  const parent = nodes.map((_, i) => i);
  const find = (x: number): number => (parent[x] === x ? x : (parent[x] = find(parent[x])));
  for (const e of edges) parent[find(e.a)] = find(e.b);
  for (;;) {
    const coreRoot = find(coreIdx);
    let best: { a: number; b: number; d: number } | null = null;
    for (const { n, i } of brain) {
      if (find(i) === coreRoot) continue;
      for (const { n: m, i: j } of brain) {
        if (find(j) !== coreRoot) continue;
        const d = dist(n, m);
        if (!best || d < best.d) best = { a: i, b: j, d };
      }
    }
    if (!best) break;
    addEdge(best.a, best.b);
    parent[find(best.a)] = find(best.b);
  }

  const stemPath = [coreIdx, ...stemIdx, verdictIdx];
  for (let s = 0; s < stemPath.length - 1; s++) addEdge(stemPath[s], stemPath[s + 1]);

  const adj = new Map<number, { to: number; edge: number }[]>();
  edges.forEach((e, idx) => {
    if (!adj.has(e.a)) adj.set(e.a, []);
    if (!adj.has(e.b)) adj.set(e.b, []);
    adj.get(e.a)!.push({ to: e.b, edge: idx });
    adj.get(e.b)!.push({ to: e.a, edge: idx });
  });

  const distTo = nodes.map(() => Infinity);
  const prev = nodes.map(() => -1);
  const done = nodes.map(() => false);
  distTo[coreIdx] = 0;
  for (;;) {
    let u = -1;
    for (let i = 0; i < nodes.length; i++) if (!done[i] && distTo[i] < Infinity && (u < 0 || distTo[i] < distTo[u])) u = i;
    if (u < 0) break;
    done[u] = true;
    for (const { to } of adj.get(u) ?? []) {
      if (nodes[to].kind === "stem" || nodes[to].kind === "verdict") continue;
      const nd = distTo[u] + dist(nodes[u], nodes[to]) * (nodes[u].kind === "member" ? 3 : 1);
      if (nd < distTo[to]) {
        distTo[to] = nd;
        prev[to] = u;
      }
    }
  }
  const memberPaths = memberIdx.map((m) => {
    const path = [m];
    let cur = m;
    while (cur !== coreIdx && prev[cur] >= 0) {
      cur = prev[cur];
      path.push(cur);
    }
    return path;
  });

  return { nodes, edges, adj, coreIdx, verdictIdx, stemPath, memberIdx, memberPaths, outline, fissure };
}

function edgeBetween(g: Graph, a: number, b: number): number {
  return g.adj.get(a)?.find((x) => x.to === b)?.edge ?? -1;
}

function makeImpulse(g: Graph, path: number[], color: RGB, strength: number, speed: number, toCore: boolean): Impulse {
  const lengths: number[] = [0];
  for (let i = 1; i < path.length; i++) lengths.push(lengths[i - 1] + dist(g.nodes[path[i - 1]], g.nodes[path[i]]));
  return { path, lengths, total: lengths[lengths.length - 1], d: 0, speed, color, strength, toCore, lastSeg: 0 };
}

function pointAt(g: Graph, imp: Impulse, d: number): [number, number] {
  const clamped = Math.max(0, Math.min(imp.total, d));
  let i = 1;
  while (i < imp.lengths.length - 1 && imp.lengths[i] < clamped) i++;
  const a = g.nodes[imp.path[i - 1]];
  const b = g.nodes[imp.path[i]];
  const seg = imp.lengths[i] - imp.lengths[i - 1] || 1;
  const t = (clamped - imp.lengths[i - 1]) / seg;
  return [a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t];
}

function glowSprite(color: RGB): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.18, `rgba(${color[0]},${color[1]},${color[2]},0.9)`);
  g.addColorStop(0.5, `rgba(${color[0]},${color[1]},${color[2]},0.22)`);
  g.addColorStop(1, `rgba(${color[0]},${color[1]},${color[2]},0)`);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  return c;
}

const rgba = (c: RGB, a: number) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

export default function TribunalBrain({ members, activeCode, onSelect, verdictLabel }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const redrawRef = useRef<(() => void) | null>(null);
  const focusRef = useRef<number | null>(null);
  const reduceMotion = useReducedMotion();
  const [hovered, setHovered] = useState<number | null>(null);
  const graph = useMemo(() => (typeof document === "undefined" ? null : buildGraph(members.length)), [members.length]);

  const activeIndex = activeCode ? members.findIndex((m) => m.code === activeCode) : -1;
  const focusIndex = hovered ?? (activeIndex >= 0 ? activeIndex : null);
  focusRef.current = focusIndex;

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap || !graph) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const sprites = new Map<string, HTMLCanvasElement>();
    const sprite = (c: RGB) => {
      const key = c.join(",");
      let s = sprites.get(key);
      if (!s) {
        s = glowSprite(c);
        sprites.set(key, s);
      }
      return s;
    };

    let scale = 1;
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const cssW = wrap.clientWidth;
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(((cssW * H) / W) * dpr);
      canvas.style.height = `${(cssW * H) / W}px`;
      scale = (cssW / W) * dpr;
    };
    resize();

    const impulses: Impulse[] = [];
    const memberTimers = members.map((_, i) => 0.4 + i * 0.35 + Math.random() * 1.2);
    let ambientTimer = 0.2;
    let coreCharge = 0;
    let running = true;
    let visible = true;
    let last = performance.now();
    let raf = 0;

    const fireMember = (i: number, strength: number) => {
      const path = graph.memberPaths[i];
      if (path.length < 2) return;
      impulses.push(makeImpulse(graph, path, KIND_COLOR[members[i].kind], strength, 210 + Math.random() * 70, true));
      graph.nodes[path[0]].heat = Math.min(1, graph.nodes[path[0]].heat + 0.9 * strength);
    };

    const fireAmbient = () => {
      const start = Math.floor(Math.random() * graph.nodes.length);
      if (graph.nodes[start].kind !== "inter") return;
      const path = [start];
      let cur = start;
      const hops = 2 + Math.floor(Math.random() * 3);
      for (let h = 0; h < hops; h++) {
        const options = (graph.adj.get(cur) ?? []).filter(({ to }) => !path.includes(to) && graph.nodes[to].kind === "inter");
        if (!options.length) break;
        cur = options[Math.floor(Math.random() * options.length)].to;
        path.push(cur);
      }
      if (path.length > 1) impulses.push(makeImpulse(graph, path, AMBIENT_COLOR, 0.35, 120 + Math.random() * 60, false));
    };

    const draw = (animated: boolean) => {
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.clearRect(0, 0, W, H);

      const focus = focusRef.current;
      const focusColor = focus !== null ? KIND_COLOR[members[focus].kind] : null;
      const focusEdges = new Set<number>();
      if (focus !== null) {
        const p = graph.memberPaths[focus];
        for (let i = 1; i < p.length; i++) focusEdges.add(edgeBetween(graph, p[i - 1], p[i]));
        for (let i = 1; i < graph.stemPath.length; i++) focusEdges.add(edgeBetween(graph, graph.stemPath[i - 1], graph.stemPath[i]));
      }

      const glow = ctx.createRadialGradient(CORE[0], CORE[1], 20, CORE[0], CORE[1], 460);
      glow.addColorStop(0, "rgba(167,139,250,0.07)");
      glow.addColorStop(1, "rgba(167,139,250,0)");
      ctx.fillStyle = glow;
      ctx.fill(graph.outline);
      ctx.lineWidth = 1.2;
      ctx.strokeStyle = "rgba(255,255,255,0.13)";
      ctx.stroke(graph.outline);
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(255,255,255,0.05)";
      ctx.stroke(graph.fissure);

      ctx.lineWidth = 0.7;
      ctx.strokeStyle = "rgba(255,255,255,0.075)";
      ctx.beginPath();
      for (const e of graph.edges) {
        const a = graph.nodes[e.a];
        const b = graph.nodes[e.b];
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
      }
      ctx.stroke();

      ctx.globalCompositeOperation = "lighter";
      graph.edges.forEach((e, idx) => {
        const onFocus = focusEdges.has(idx);
        const lit = Math.max(e.heat, onFocus ? (animated ? 0.28 : 0.45) : 0);
        if (lit < 0.02) return;
        const a = graph.nodes[e.a];
        const b = graph.nodes[e.b];
        ctx.lineWidth = 0.8 + lit * 1.4;
        ctx.strokeStyle = rgba(onFocus && focusColor ? focusColor : e.color, Math.min(0.75, lit * 0.7));
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      });

      for (const n of graph.nodes) {
        if (n.kind !== "inter" && n.kind !== "stem") continue;
        ctx.fillStyle = `rgba(220,225,255,${0.28 + n.heat * 0.6})`;
        ctx.beginPath();
        ctx.arc(n.x, n.y, 1.7 + n.heat * 1.6, 0, Math.PI * 2);
        ctx.fill();
        if (n.heat > 0.05) {
          const s = 14 + n.heat * 18;
          ctx.globalAlpha = n.heat * 0.5;
          ctx.drawImage(sprite(AMBIENT_COLOR), n.x - s / 2, n.y - s / 2, s, s);
          ctx.globalAlpha = 1;
        }
      }

      graph.memberIdx.forEach((ni, i) => {
        const n = graph.nodes[ni];
        const c = KIND_COLOR[members[i].kind];
        const h = Math.max(n.heat, focus === i ? 0.55 : 0);
        const s = 34 + h * 46;
        ctx.globalAlpha = 0.35 + h * 0.65;
        ctx.drawImage(sprite(c), n.x - s / 2, n.y - s / 2, s, s);
        ctx.globalAlpha = 1;
        ctx.fillStyle = rgba(c, 0.95);
        ctx.beginPath();
        ctx.arc(n.x, n.y, 4.2 + h * 1.8, 0, Math.PI * 2);
        ctx.fill();
      });

      const core = graph.nodes[graph.coreIdx];
      const coreSize = 70 + core.heat * 70;
      ctx.globalAlpha = 0.55 + core.heat * 0.45;
      ctx.drawImage(sprite(CORE_COLOR), core.x - coreSize / 2, core.y - coreSize / 2, coreSize, coreSize);

      const verdict = graph.nodes[graph.verdictIdx];
      const vSize = 46 + verdict.heat * 80;
      ctx.globalAlpha = 0.45 + verdict.heat * 0.55;
      ctx.drawImage(sprite(VERDICT_COLOR), verdict.x - vSize / 2, verdict.y - vSize / 2, vSize, vSize);
      ctx.globalAlpha = 1;

      for (const imp of impulses) {
        const steps = 9;
        for (let k = steps; k >= 1; k--) {
          const [x, y] = pointAt(graph, imp, imp.d - k * 7);
          ctx.fillStyle = rgba(imp.color, (1 - k / (steps + 1)) * 0.5 * imp.strength);
          ctx.beginPath();
          ctx.arc(x, y, 1.3 + (1 - k / steps) * 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
        const [hx, hy] = pointAt(graph, imp, imp.d);
        const s = 18 + 14 * imp.strength;
        ctx.globalAlpha = Math.min(1, 0.4 + imp.strength);
        ctx.drawImage(sprite(imp.color), hx - s / 2, hy - s / 2, s, s);
        ctx.globalAlpha = 1;
      }
      ctx.globalCompositeOperation = "source-over";
    };

    const step = (dt: number) => {
      const decay = Math.exp(-dt * 1.6);
      const slow = Math.exp(-dt * 1.1);
      for (const e of graph.edges) e.heat *= decay;
      for (const n of graph.nodes) n.heat *= n.kind === "core" || n.kind === "verdict" ? slow : decay;

      const focus = focusRef.current;
      memberTimers.forEach((t, i) => {
        memberTimers[i] = t - dt;
        if (memberTimers[i] > 0) return;
        fireMember(i, focus === i ? 1 : 0.85);
        const mean = focus === i ? 0.9 : focus !== null ? 4.2 : 2.6;
        memberTimers[i] = mean * (0.55 + Math.random() * 0.9);
      });
      ambientTimer -= dt;
      if (ambientTimer <= 0) {
        fireAmbient();
        ambientTimer = 0.18 + Math.random() * 0.35;
      }

      for (let i = impulses.length - 1; i >= 0; i--) {
        const imp = impulses[i];
        imp.d += imp.speed * dt;
        let seg = 1;
        while (seg < imp.lengths.length - 1 && imp.lengths[seg] < imp.d) seg++;
        for (let s = imp.lastSeg; s < seg; s++) {
          const e = edgeBetween(graph, imp.path[s], imp.path[s + 1]);
          if (e >= 0) {
            graph.edges[e].heat = Math.min(1, graph.edges[e].heat + 0.85 * imp.strength);
            graph.edges[e].color = imp.color;
          }
          if (s > 0) graph.nodes[imp.path[s]].heat = Math.min(1, graph.nodes[imp.path[s]].heat + 0.5 * imp.strength);
        }
        imp.lastSeg = Math.max(imp.lastSeg, seg);
        if (imp.d < imp.total) continue;
        const end = imp.path[imp.path.length - 1];
        graph.nodes[end].heat = Math.min(1, graph.nodes[end].heat + 0.35 * imp.strength);
        if (imp.toCore && end === graph.coreIdx) {
          coreCharge += imp.strength;
          if (coreCharge >= 2.4) {
            coreCharge = 0;
            impulses.push(makeImpulse(graph, graph.stemPath, VERDICT_COLOR, 1, 160, false));
          }
        }
        impulses.splice(i, 1);
      }
    };

    const loop = (now: number) => {
      if (!running) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (visible) {
        step(dt);
        draw(true);
      }
      raf = requestAnimationFrame(loop);
    };

    redrawRef.current = reduceMotion ? () => draw(false) : null;

    const ro = new ResizeObserver(() => {
      resize();
      draw(!reduceMotion);
    });
    ro.observe(wrap);

    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      last = performance.now();
    });
    io.observe(wrap);

    if (reduceMotion) draw(false);
    else raf = requestAnimationFrame(loop);

    return () => {
      running = false;
      redrawRef.current = null;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
    };
  }, [graph, members, reduceMotion]);

  useEffect(() => {
    redrawRef.current?.();
  }, [focusIndex]);

  if (!graph) return null;

  const focusMember = focusIndex !== null ? members[focusIndex] : null;

  return (
    <div ref={wrapRef} className="relative w-full select-none">
      <canvas ref={canvasRef} className="block w-full" aria-hidden="true" />
      {graph.memberIdx.map((ni, i) => {
        const n = graph.nodes[ni];
        const m = members[i];
        const leftSide = n.x < CORE[0];
        return (
          <button
            key={m.code}
            type="button"
            aria-label={`${m.name}: ${m.tag}`}
            aria-pressed={activeCode === m.code}
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            onFocus={() => setHovered(i)}
            onBlur={() => setHovered(null)}
            onClick={() => onSelect(m.code)}
            className="absolute -translate-x-1/2 -translate-y-1/2 w-9 h-9 rounded-full focus:outline-none focus-visible:ring-1 focus-visible:ring-signal-amber/70"
            style={{ left: `${(n.x / W) * 100}%`, top: `${(n.y / H) * 100}%` }}
          >
            <span
              className={`pointer-events-none absolute top-1/2 -translate-y-1/2 whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.14em] transition-colors duration-300 ${
                leftSide ? "right-full mr-1 text-right" : "left-full ml-1 text-left"
              } ${focusIndex === i ? "text-ink-50" : "text-ink-300"}`}
            >
              <span className="text-ink-500 mr-1.5 tabular-nums">{m.code}</span>
              <span className="hidden sm:inline">{m.short}</span>
            </span>
          </button>
        );
      })}
      <div
        className="pointer-events-none absolute -translate-x-1/2 font-mono text-[9px] uppercase tracking-[0.2em] text-signal-cyan/70 whitespace-nowrap"
        style={{ left: `${(CORE[0] / W) * 100}%`, top: `${((CORE[1] + 30) / H) * 100}%` }}
      >
        weighted vote
      </div>
      <div
        className="pointer-events-none absolute -translate-x-1/2 text-center whitespace-nowrap"
        style={{ left: `${(VERDICT[0] / W) * 100}%`, top: `${((VERDICT[1] + 22) / H) * 100}%` }}
      >
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-signal-amber">Verdict</div>
        <div className="font-mono text-[9px] uppercase tracking-[0.16em] text-ink-600 mt-0.5">{verdictLabel}</div>
      </div>
      <div className="pointer-events-none absolute left-0 bottom-0 max-w-[44%] min-h-[3.5rem]" aria-live="polite">
        {focusMember && (
          <>
            <div className="font-display text-lg sm:text-2xl text-ink-50 leading-tight">{focusMember.name}</div>
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-400 mt-1">{focusMember.tag}</div>
          </>
        )}
      </div>
    </div>
  );
}
