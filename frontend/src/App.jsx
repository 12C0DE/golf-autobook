import React, { useState } from 'react';

export default function App() {
  const [targetDate, setTargetDate] = useState('2026-08-30');
  const [playerCount, setPlayerCount] = useState(2);
  const [selectedCourse, setSelectedCourse] = useState('ALL');
  const [earliestTime, setEarliestTime] = useState('07:00');
  const [latestTime, setLatestTime] = useState('11:00');
  const [memberId, setMemberId] = useState('1129941');
  const [email, setEmail] = useState('rubenhnt@gmail.com');
  const [name, setName] = useState('Ruben Hernandez');
  const [apiUrl, setApiUrl] = useState('https://YOUR_API_GATEWAY_URL/prod/book');
  
  const [logs, setLogs] = useState([
    { type: 'info', text: 'GOLF-AUTOBOOK SYSTEM // v1.2.0 initialized' },
    { type: 'accent', text: 'Target Group: Wichita Municipal (ID: 8)' },
    { type: 'muted', text: 'Standing by for schedule trigger or direct execution...' }
  ]);
  const [loading, setLoading] = useState(false);

  const courseMap = {
    'ALL': [],
    'Auburn Hills': [8905],
    'MacDonald': [9001],
    'Tex Consolver': [9027],
    'Arthur B. Sim': [8903]
  };

  const handleExecute = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const payload = {
      targetDate,
      playerCount: parseInt(playerCount, 10),
      preferredCourses: courseMap[selectedCourse],
      timeWindow: { earliestTime, latestTime },
      memberProfileId: parseInt(memberId, 10),
      email,
      name,
      golfClubGroupId: 8
    };

    setLogs(prev => [
      ...prev,
      { type: 'command', text: `>> DISPATCH -> ${targetDate} (${selectedCourse})` },
      { type: 'muted', text: `Payload: ${JSON.stringify(payload)}` }
    ]);

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      setLogs(prev => [
        ...prev,
        { type: 'success', text: `[200 OK] Reservation Confirmed: ${data.confirmationNumber || data.response?.confirmationNumber || 'Success'}` },
        { type: 'muted', text: JSON.stringify(data, null, 2) }
      ]);
    } catch (err) {
      setLogs(prev => [...prev, { type: 'error', text: `[ERR] Request Failed: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gruvbox-bg0 text-gruvbox-fg p-4 md:p-8 flex items-center justify-center">
      <div className="w-full max-w-5xl bg-gruvbox-bg1 border border-gruvbox-bg3 rounded-lg shadow-2xl overflow-hidden">
        
        <div className="bg-gruvbox-bg2 px-6 py-4 border-b border-gruvbox-bg3 flex flex-wrap justify-between items-center gap-4">
          <div className="flex items-center space-x-3">
            <span className="w-3.5 h-3.5 rounded-full bg-gruvbox-red inline-block"></span>
            <span className="w-3.5 h-3.5 rounded-full bg-gruvbox-yellow inline-block"></span>
            <span className="w-3.5 h-3.5 rounded-full bg-gruvbox-green inline-block"></span>
            <h1 className="font-mono text-sm font-semibold tracking-wide text-gruvbox-fg pl-2">
              golf-autobook <span className="text-gruvbox-gray font-normal">// console.gruvbox</span>
            </h1>
          </div>
          <div className="flex items-center space-x-2 text-xs font-mono">
            <span className="px-2.5 py-1 bg-gruvbox-bg3 text-gruvbox-aqua rounded border border-gruvbox-bg4">
              API: READY
            </span>
            <span className="px-2.5 py-1 bg-gruvbox-bg3 text-gruvbox-orange rounded border border-gruvbox-bg4">
              CLUSTER: us-east-2
            </span>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
          <form onSubmit={handleExecute} className="lg:col-span-7 space-y-4">
            <div className="border border-gruvbox-bg3 bg-gruvbox-bg1 p-4 rounded-md space-y-4">
              <h2 className="text-xs font-mono uppercase tracking-wider text-gruvbox-yellow font-bold border-b border-gruvbox-bg3 pb-2">
                1. Booking Parameters
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gruvbox-gray mb-1">Target Date</label>
                  <input 
                    type="date" 
                    value={targetDate} 
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-sm focus:outline-none focus:border-gruvbox-yellow transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gruvbox-gray mb-1">Target Course</label>
                  <select 
                    value={selectedCourse} 
                    onChange={(e) => setSelectedCourse(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-sm focus:outline-none focus:border-gruvbox-yellow transition-colors cursor-pointer"
                  >
                    <option value="ALL">-- Auto-Scan All Courses --</option>
                    <option value="Auburn Hills">Auburn Hills (8905)</option>
                    <option value="MacDonald">MacDonald (9001)</option>
                    <option value="Tex Consolver">Tex Consolver (9027)</option>
                    <option value="Arthur B. Sim">Arthur B. Sim (8903)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gruvbox-gray mb-1">Player Count</label>
                  <select 
                    value={playerCount} 
                    onChange={(e) => setPlayerCount(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-sm focus:outline-none focus:border-gruvbox-yellow transition-colors cursor-pointer"
                  >
                    <option value={1}>1 Player</option>
                    <option value={2}>2 Players</option>
                    <option value={3}>3 Players</option>
                    <option value={4}>4 Players</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gruvbox-gray mb-1">Earliest Time</label>
                  <input 
                    type="time" 
                    value={earliestTime} 
                    onChange={(e) => setEarliestTime(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-sm focus:outline-none focus:border-gruvbox-yellow transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gruvbox-gray mb-1">Latest Time</label>
                  <input 
                    type="time" 
                    value={latestTime} 
                    onChange={(e) => setLatestTime(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-sm focus:outline-none focus:border-gruvbox-yellow transition-colors"
                  />
                </div>
              </div>
            </div>

            <div className="border border-gruvbox-bg3 bg-gruvbox-bg1 p-4 rounded-md space-y-4">
              <h2 className="text-xs font-mono uppercase tracking-wider text-gruvbox-blue font-bold border-b border-gruvbox-bg3 pb-2">
                2. Member Credentials & API Gateway
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gruvbox-gray mb-1">Member Profile ID</label>
                  <input 
                    type="text" 
                    value={memberId} 
                    onChange={(e) => setMemberId(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-sm focus:outline-none focus:border-gruvbox-blue transition-colors font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gruvbox-gray mb-1">Member Email</label>
                  <input 
                    type="email" 
                    value={email} 
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-sm focus:outline-none focus:border-gruvbox-blue transition-colors font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gruvbox-gray mb-1">API Endpoint URL</label>
                <input 
                  type="text" 
                  value={apiUrl} 
                  onChange={(e) => setApiUrl(e.target.value)}
                  className="w-full bg-gruvbox-bg0 border border-gruvbox-bg4 text-gruvbox-fg rounded px-3 py-2 text-xs focus:outline-none focus:border-gruvbox-blue transition-colors font-mono"
                />
              </div>
            </div>

            <button 
              type="submit" 
              disabled={loading}
              className="w-full bg-gruvbox-yellowDark hover:bg-gruvbox-yellow text-gruvbox-bg1 font-bold py-3 px-4 rounded shadow-md transition-all font-mono text-sm tracking-wider uppercase disabled:opacity-50 cursor-pointer"
            >
              {loading ? 'Executing Lock & Reserve Pipeline...' : '⚡ Trigger Immediate Booking'}
            </button>
          </form>

          <div className="lg:col-span-5 flex flex-col">
            <div className="flex-1 bg-gruvbox-bg0 border border-gruvbox-bg3 rounded-md p-4 flex flex-col font-mono text-xs shadow-inner min-h-[350px]">
              <div className="flex justify-between items-center pb-2 mb-3 border-b border-gruvbox-bg3 text-gruvbox-gray">
                <span>// ACTIVITY LOG</span>
                <span className="text-gruvbox-aqua">● LIVE STREAM</span>
              </div>
              
              <div className="flex-1 overflow-y-auto space-y-2 max-h-[380px] pr-2">
                {logs.map((log, index) => {
                  let colorClass = 'text-gruvbox-fg';
                  if (log.type === 'command') colorClass = 'text-gruvbox-yellow font-bold';
                  if (log.type === 'accent') colorClass = 'text-gruvbox-aqua';
                  if (log.type === 'success') colorClass = 'text-gruvbox-green font-bold';
                  if (log.type === 'error') colorClass = 'text-gruvbox-red font-bold';
                  if (log.type === 'muted') colorClass = 'text-gruvbox-dim';

                  return (
                    <div key={index} className={`whitespace-pre-wrap leading-relaxed ${colorClass}`}>
                      {log.text}
                    </div>
                  );
                })}
                {loading && (
                  <div className="text-gruvbox-orange animate-pulse">
                    &gt;&gt; Acquiring AppSync broadcast lock & REST server hold...
                  </div>
                )}
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
