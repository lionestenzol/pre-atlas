export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-zinc-950 text-zinc-100">
      <h1 className="text-3xl font-bold mb-2">Mosaic Dashboard</h1>
      <p className="text-zinc-500 mb-8">Port 3000 — Proxy layer active</p>
      <div className="space-y-1 text-sm font-mono text-zinc-400">
        <p>/api/delta/*    → :3001 (delta-kernel)</p>
        <p>/api/mirofish/* → :3003 (MiroFish)</p>
        <p>/api/mosaic/*   → :3005 (orchestrator)</p>
      </div>
    </main>
  );
}
