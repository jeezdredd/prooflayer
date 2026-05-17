import { useEffect, useState } from "react";
import { MeshGradient } from "@paper-design/shaders-react";
import { animate, useMotionValue } from "motion/react";
import { useShaderStore } from "../../stores/shaderStore";

interface ShaderBackgroundProps {
  variant?: "paper" | "amber" | "noir" | "dawn";
  className?: string;
  vignette?: boolean;
}

const VARIANTS = {
  paper: {
    colors: ["#f0e6d0", "#d4b884", "#8a6438", "#1a0f08"],
    bg: "#ede3cc",
    blur: 30,
    settle: 0.35,
  },
  amber: {
    colors: ["#f0d9a8", "#c08442", "#5a3618", "#0a0604"],
    bg: "#0a0604",
    blur: 0,
    settle: 0.4,
  },
  noir: {
    colors: ["#000000", "#1a1a1a", "#3a3a3a", "#f0f0f0"],
    bg: "#000000",
    blur: 0,
    settle: 0.4,
  },
  dawn: {
    colors: ["#0a0a0a", "#2a2520", "#9b7a4b", "#f5e6d0"],
    bg: "#0a0a0a",
    blur: 0,
    settle: 0.4,
  },
} as const;

const KICKOFF_SPEED = 4.0;
const KICKOFF_DURATION = 3.2;
const BOOST_SPEED = 5.5;
const BOOST_DURATION = 2.8;

export default function ShaderBackground({
  variant = "noir",
  className = "",
  vignette = true,
}: ShaderBackgroundProps) {
  const cfg = VARIANTS[variant];
  const isDark = variant !== "paper";
  const speedMV = useMotionValue(KICKOFF_SPEED);
  const [speed, setSpeed] = useState(KICKOFF_SPEED);
  const boostToken = useShaderStore((s) => s.boostToken);

  useEffect(() => {
    const unsub = speedMV.on("change", (v) => setSpeed(v));
    const ctrl = animate(speedMV, cfg.settle, {
      duration: KICKOFF_DURATION,
      ease: [0.16, 1, 0.3, 1],
    });
    return () => {
      ctrl.stop();
      unsub();
    };
  }, [cfg.settle, speedMV]);

  useEffect(() => {
    if (boostToken === 0) return;
    speedMV.set(BOOST_SPEED);
    const ctrl = animate(speedMV, cfg.settle, {
      duration: BOOST_DURATION,
      ease: [0.16, 1, 0.3, 1],
    });
    return () => ctrl.stop();
  }, [boostToken, cfg.settle, speedMV]);

  return (
    <div
      className={`fixed inset-0 pointer-events-none overflow-hidden ${className}`}
      style={{ zIndex: 0 }}
      aria-hidden="true"
    >
      <div className="absolute inset-0" style={{ background: cfg.bg }} />
      <div
        className="absolute inset-0"
        style={cfg.blur ? { filter: `blur(${cfg.blur}px)`, transform: "scale(1.15)" } : undefined}
      >
        <MeshGradient
          className="w-full h-full"
          colors={cfg.colors as unknown as string[]}
          speed={speed}
        />
      </div>
      {vignette && (
        <>
          <div
            className="absolute inset-0"
            style={{
              background: isDark
                ? "radial-gradient(ellipse 90% 70% at 50% 50%, transparent 0%, rgba(0,0,0,0.65) 90%)"
                : "radial-gradient(ellipse 100% 70% at 50% 50%, rgba(250,247,238,0.20) 0%, rgba(250,247,238,0.08) 60%, transparent 100%)",
            }}
          />
          {isDark && (
            <div
              className="absolute inset-0"
              style={{
                background:
                  "linear-gradient(to bottom, rgba(5,6,8,0.45) 0%, rgba(5,6,8,0.25) 30%, rgba(5,6,8,0.25) 70%, rgba(5,6,8,0.45) 100%)",
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
