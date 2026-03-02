import { useEffect, useRef } from "react";

export function Waveform({ active, audioLevel }: { active: boolean; audioLevel?: number | null }) {
  const cRef = useRef<HTMLCanvasElement>(null);
  const fRef = useRef<number | null>(null);
  const bars = useRef(Array.from({ length: 24 }, () => 0.1));

  useEffect(() => {
    const c = cRef.current;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    const W = c.width;
    const H = c.height;
    const b = bars.current;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      const bW = 2;
      const g = 1.5;
      const st = (W - b.length * (bW + g)) / 2;
      for (let i = 0; i < b.length; i++) {
        const target = audioLevel != null
          ? (audioLevel * 0.85 + 0.15) * (0.7 + Math.random() * 0.3)
          : (active ? Math.random() * 0.85 + 0.15 : 0.08);
        b[i] += (target - b[i]) * (active ? 0.18 : 0.1);
        const h = b[i] * H;
        const x = st + i * (bW + g);
        const y = (H - h) / 2;
        ctx.fillStyle = active
          ? `rgba(13,${Math.floor(148 + b[i] * 60)},136,${0.6 + b[i] * 0.4})`
          : `rgba(148,163,184,0.4)`;
        ctx.beginPath();
        ctx.roundRect(x, y, bW, h, 1);
        ctx.fill();
      }
      fRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      if (fRef.current) cancelAnimationFrame(fRef.current);
    };
  }, [active, audioLevel]);

  return <canvas ref={cRef} width={90} height={26} className="block" />;
}
