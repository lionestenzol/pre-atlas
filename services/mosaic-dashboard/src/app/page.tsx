import ModePanel from '@/components/ModePanel';
import UsageCounter from '@/components/UsageCounter';
import FestivalPanel from '@/components/FestivalPanel';
import SimulationPanel from '@/components/SimulationPanel';
import AtlasClusters from '@/components/AtlasClusters';

export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <h1 className="text-2xl font-bold mb-6">Mosaic Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <ModePanel />
        <UsageCounter />
        <FestivalPanel />
        <SimulationPanel />
        <AtlasClusters />
      </div>
    </main>
  );
}
