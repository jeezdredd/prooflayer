import { useEffect, useRef } from "react";

const RINGS = 9;

function buildPoints() {
  const points: Array<[number, number, number]> = [];
  for (let i = 1; i < RINGS; i++) {
    const lat = -Math.PI / 2 + (i * Math.PI) / RINGS;
    const radius = Math.cos(lat);
    const count = Math.max(6, Math.round(radius * 16));
    for (let j = 0; j < count; j++) {
      const lon = (j / count) * Math.PI * 2;
      points.push([radius * Math.cos(lon), Math.sin(lat), radius * Math.sin(lon)]);
    }
  }
  return points;
}

const POINTS = buildPoints();
const TILT = 0.38;

export default function SearchingOrb({ size = 20 }: { size?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const px = Math.round(size * dpr);
    canvas.width = px;
    canvas.height = px;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const center = px / 2;
    const sphere = center * 0.86;
    const dot = Math.max(0.55, px * 0.026);
    const cosT = Math.cos(TILT);
    const sinT = Math.sin(TILT);
    let frame = 0;

    const draw = (time: number) => {
      const t = time / 1000;
      const spin = t * 0.9;
      const cosA = Math.cos(spin);
      const sinA = Math.sin(spin);
      const theta = Math.sin(t * 1.6) * 0.95;
      const phi = Math.sin(t * 2.3) * 0.18;
      const sx = Math.cos(phi) * Math.sin(theta);
      const sy = Math.sin(phi);
      const sz = Math.cos(phi) * Math.cos(theta);
      ctx.clearRect(0, 0, px, px);
      for (const [x0, y0, z0] of POINTS) {
        const x = x0 * cosA + z0 * sinA;
        const z1 = -x0 * sinA + z0 * cosA;
        const y = y0 * cosT - z1 * sinT;
        const z = y0 * sinT + z1 * cosT;
        if (z < -0.2) continue;
        const depth = (z + 1) / 2;
        const near = Math.max(0, x * sx + y * sy + z * sz - 0.72) / 0.28;
        const glow = near * near;
        ctx.fillStyle = `rgba(255,255,255,${Math.min(1, 0.1 + 0.32 * depth + 0.65 * glow)})`;
        ctx.beginPath();
        ctx.arc(center + x * sphere, center - y * sphere, dot * (0.7 + 0.4 * depth + 0.55 * glow), 0, Math.PI * 2);
        ctx.fill();
      }
      if (!still) frame = requestAnimationFrame(draw);
    };

    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [size]);

  return <canvas ref={ref} style={{ width: size, height: size }} className="shrink-0" aria-hidden="true" />;
}
