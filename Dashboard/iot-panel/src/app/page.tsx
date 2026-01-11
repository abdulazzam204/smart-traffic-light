import TrafficDashboard from "@/components/TrafficDashboard";

export default function Home() {
  const streamUrl = process.env.NEXT_PUBLIC_STREAM_URL ?? "";

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Osman Kavuncu Boulevard</h1>
          <p>Smart Traffic Control Center</p>
        </div>
        <span className="badge">TinyML</span>
      </header>
      <TrafficDashboard streamUrl={streamUrl} />
    </main>
  );
}
