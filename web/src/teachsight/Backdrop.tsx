/** Lightweight still background. Replaces the GPU shader so training keeps the graphics card and the screen never flickers. */
export default function Backdrop() {
  return <div className="bd" aria-hidden="true"><div className="bd-base" /><div className="bd-grain" /></div>;
}
