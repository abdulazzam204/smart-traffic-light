"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import StreamPlayer from "./StreamPlayer";

type TrafficState = {
  lane1_count: number;
  lane2_count: number;
  lane3_count: number;
  lane4_count: number;
};

type TrafficDashboardProps = {
  streamUrl: string;
};

const laneConfig = [
  {
    key: "lane1_count",
    name: "North",
    detail: "North Entry",
    light: "Signal 1",
  },
  {
    key: "lane2_count",
    name: "East",
    detail: "East Entry",
    light: "Signal 2",
  },
  {
    key: "lane3_count",
    name: "South",
    detail: "South Entry",
    light: "Signal 3",
  },
  {
    key: "lane4_count",
    name: "West",
    detail: "West Entry",
    light: "Signal 4",
  },
] as const;

const emptyState: TrafficState = {
  lane1_count: 0,
  lane2_count: 0,
  lane3_count: 0,
  lane4_count: 0,
};

const withDelay = (delay: string): CSSProperties =>
  ({
    "--delay": delay,
  } as CSSProperties);

export default function TrafficDashboard({ streamUrl }: TrafficDashboardProps) {
  const [traffic, setTraffic] = useState<TrafficState | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const fetchTraffic = async () => {
      try {
        const response = await fetch("/api/traffic", {
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error("traffic server not reachable");
        }
        const data = (await response.json()) as TrafficState;
        if (!mounted) return;
        setTraffic(data);
        setLastUpdated(new Date());
        setError(null);
      } catch (err) {
        if (!mounted) return;
        setError("Offline");
      }
    };

    fetchTraffic();
    const timer = window.setInterval(fetchTraffic, 2000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  const snapshot = traffic ?? emptyState;
  const counts = laneConfig.map((lane) => snapshot[lane.key]);
  const totalCount = counts.reduce((sum, count) => sum + count, 0);
  const maxCount = Math.max(...counts, 1);

  const priority = useMemo(() => {
    if (!traffic) return null;
    const max = Math.max(...counts);
    if (max === 0) return null;
    const idx = counts.findIndex((value) => value === max);
    return idx >= 0 ? laneConfig[idx] : null;
  }, [counts, traffic]);

  return (
    <section className="grid">
      <div className="card feed-card" style={withDelay("0.1s")}>
        <div className="card-head">
          <div>
            <h2>Live Camera</h2>
            <p>Osman Kavuncu Boulevard - live traffic flow</p>
          </div>
          <span className={`status ${error ? "status--bad" : "status--good"}`}>
            {error ? "Offline" : "Live"}
          </span>
        </div>
        <StreamPlayer defaultUrl={streamUrl} />
        <p className="footer-note">
          Last update:{" "}
          {lastUpdated
            ? lastUpdated.toLocaleTimeString("en-GB")
            : "--:--"}
        </p>
      </div>

      <div className="card summary-card" style={withDelay("0.2s")}>
        <div className="card-head">
          <div>
            <h2>Operations Summary</h2>
            <p>IoT control room - TinyML mode</p>
          </div>
        </div>
        <div className="stats-row">
          <div className="stat-tile">
            <span>Total Vehicles</span>
            <strong>{totalCount}</strong>
          </div>
          <div className="stat-tile">
            <span>Priority Lane</span>
            <strong>{priority ? priority.name : "-"}</strong>
          </div>
          <div className="stat-tile">
            <span>Status</span>
            <strong>{error ? "Idle" : "Monitoring"}</strong>
          </div>
        </div>
        <p className="footer-note">
          Highest demand lane will receive green-light priority in the
          control system.
        </p>
      </div>

      <div className="card junction-card" style={withDelay("0.3s")}>
        <div className="card-head">
          <div>
            <h3>Junction Map</h3>
            <p>Live load per signal cluster</p>
          </div>
        </div>
        <div className="junction">
          <span className="road horizontal" />
          <span className="road vertical" />
          <div className="node north">
            North
            <strong>{snapshot.lane1_count}</strong>
          </div>
          <div className="node east">
            East
            <strong>{snapshot.lane2_count}</strong>
          </div>
          <div className="node south">
            South
            <strong>{snapshot.lane3_count}</strong>
          </div>
          <div className="node west">
            West
            <strong>{snapshot.lane4_count}</strong>
          </div>
        </div>
      </div>

      <div className="lane-grid">
        {laneConfig.map((lane, index) => {
          const count = snapshot[lane.key];
          const isPriority = priority?.key === lane.key;
          const meterWidth = Math.min(100, (count / maxCount) * 100);
          return (
            <div
              key={lane.key}
              className={`card lane-card ${isPriority ? "priority" : ""}`}
              data-lane={`lane${index + 1}`}
              style={withDelay(`${0.4 + index * 0.1}s`)}
            >
              <div className="lane-header">
                <div>
                  <div className="lane-title">{lane.name}</div>
                  <div className="lane-sub">{lane.detail}</div>
                </div>
                <div className="lane-count">{count}</div>
              </div>
              <div className="lane-sub">{lane.light}</div>
              <div className="lane-meter">
                <span style={{ width: `${meterWidth}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
