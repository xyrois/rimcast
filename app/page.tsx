'use client';

import { useEffect, useMemo, useState } from 'react';

interface PlayerRecord {
  id: number;
  name: string;
  team: string;
  current: {
    gp: number;
    min: number;
    pts: number;
    reb: number;
    ast: number;
  };
  ros_forecast: {
    proj_pts_avg: number;
    proj_reb_avg: number;
    proj_ast_avg: number;
    end_season_pts_avg: number;
    rem_games: number;
  };
}

export default function HomePage() {
  const [players, setPlayers] = useState<PlayerRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTeam, setSelectedTeam] = useState('ALL');
  const [activeStat, setActiveStat] = useState<'pts' | 'reb' | 'ast'>('pts');
  const [sortBy, setSortBy] = useState<'proj' | 'current' | 'name'>('proj');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch('/data/forecasts.json')
      .then((res) => res.json())
      .then((data: PlayerRecord[]) => {
        setPlayers(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load forecasts:', err);
        setIsLoading(false);
      });
  }, []);

  const teams = useMemo(() => {
    const unique = Array.from(new Set(players.map((p) => p.team))).filter(Boolean).sort();
    return ['ALL', ...unique];
  }, [players]);

  const filteredPlayers = useMemo(() => {
    return players
      .filter((p) => {
        const matchesSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesTeam = selectedTeam === 'ALL' || p.team === selectedTeam;
        return matchesSearch && matchesTeam;
      })
      .sort((a, b) => {
        if (sortBy === 'name') return a.name.localeCompare(b.name);

        const currentA = a.current[activeStat];
        const currentB = b.current[activeStat];

        const projA =
          activeStat === 'pts'
            ? a.ros_forecast.proj_pts_avg
            : activeStat === 'reb'
            ? a.ros_forecast.proj_reb_avg
            : a.ros_forecast.proj_ast_avg;

        const projB =
          activeStat === 'pts'
            ? b.ros_forecast.proj_pts_avg
            : activeStat === 'reb'
            ? b.ros_forecast.proj_reb_avg
            : b.ros_forecast.proj_ast_avg;

        if (sortBy === 'current') return currentB - currentA;
        return projB - projA;
      });
  }, [players, searchQuery, selectedTeam, sortBy, activeStat]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-zinc-300 font-sans">
        <p className="animate-pulse tracking-wide">Loading player forecasts...</p>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6 md:p-12 font-sans">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Rimcast</h1>
            <p className="text-sm text-zinc-400 mt-1">
              NBA Player Statistics & Empirical Bayes Rest-of-Season Projections
            </p>
          </div>
          <div className="text-xs text-zinc-500 font-mono">
            {players.length} Total Players Tracked
          </div>
        </header>

        {/* Controls */}
        <div className="flex flex-col md:flex-row gap-3 justify-between items-stretch">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 flex-1">
            <input
              type="text"
              placeholder="Search player name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-500"
            />

            <select
              value={selectedTeam}
              onChange={(e) => setSelectedTeam(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
            >
              {teams.map((team) => (
                <option key={team} value={team}>
                  {team === 'ALL' ? 'All Teams' : team}
                </option>
              ))}
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
            >
              <option value="proj">Sort: Projected ROS (High to Low)</option>
              <option value="current">Sort: Current Stat (High to Low)</option>
              <option value="name">Sort: Player Name (A-Z)</option>
            </select>
          </div>

          {/* Metric Selector Tabs */}
          <div className="flex bg-zinc-900 border border-zinc-800 rounded-lg p-1 self-start md:self-auto">
            {(['pts', 'reb', 'ast'] as const).map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveStat(cat)}
                className={`px-4 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider transition-colors ${
                  activeStat === cat
                    ? 'bg-zinc-800 text-sky-400 border border-zinc-700'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/40">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900/90 text-zinc-400 text-xs uppercase tracking-wider border-b border-zinc-800">
              <tr>
                <th className="py-3 px-4">Player</th>
                <th className="py-3 px-4">Team</th>
                <th className="py-3 px-4 text-right">GP</th>
                <th className="py-3 px-4 text-right">MPG</th>
                <th className="py-3 px-4 text-right">Current {activeStat.toUpperCase()}</th>
                <th className="py-3 px-4 text-right">Projected ROS {activeStat.toUpperCase()}</th>
                <th className="py-3 px-4 text-right">Proj Delta</th>
                <th className="py-3 px-4 text-right">Projected 82G Finish</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60">
              {filteredPlayers.slice(0, 100).map((player) => {
                const currentVal = player.current[activeStat];
                const projVal =
                  activeStat === 'pts'
                    ? player.ros_forecast.proj_pts_avg
                    : activeStat === 'reb'
                    ? player.ros_forecast.proj_reb_avg
                    : player.ros_forecast.proj_ast_avg;

                const delta = (projVal - currentVal).toFixed(1);
                const isPositive = Number(delta) > 0;
                const isNeutral = Number(delta) === 0;

                const finalSeasonEst =
                  activeStat === 'pts'
                    ? player.ros_forecast.end_season_pts_avg.toFixed(1)
                    : (
                        ((currentVal * player.current.gp) +
                          projVal * player.ros_forecast.rem_games) /
                        82
                      ).toFixed(1);

                return (
                  <tr key={player.id} className="hover:bg-zinc-800/40 transition-colors">
                    <td className="py-3 px-4 font-medium text-zinc-100">
                      <div className="flex items-center gap-3">
                        <img
                          src={`https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${player.id}.png&w=96&h=70`}
                          alt={player.name}
                          className="w-8 h-8 rounded-full object-cover bg-zinc-800 shrink-0"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                        <span>{player.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-zinc-400 font-mono text-xs">{player.team}</td>
                    <td className="py-3 px-4 text-right text-zinc-300 font-mono">{player.current.gp}</td>
                    <td className="py-3 px-4 text-right text-zinc-400 font-mono">{player.current.min}</td>
                    <td className="py-3 px-4 text-right text-zinc-300 font-mono">{currentVal.toFixed(1)}</td>
                    <td className="py-3 px-4 text-right font-semibold text-sky-400 font-mono">
                      {projVal.toFixed(1)}
                    </td>
                    <td
                      className={`py-3 px-4 text-right font-mono text-xs ${
                        isNeutral
                          ? 'text-zinc-500'
                          : isPositive
                          ? 'text-emerald-400'
                          : 'text-rose-400'
                      }`}
                    >
                      {isPositive ? `+${delta}` : delta}
                    </td>
                    <td className="py-3 px-4 text-right text-zinc-400 font-mono">{finalSeasonEst}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}