import React, { useState, useRef, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'https://YOUR_API_GATEWAY_URL/prod/book';
const MEMBER_PROFILE_ID = 1129941;
const MEMBER_EMAIL = 'rubenhnt@gmail.com';
const MEMBER_NAME = 'Ruben Hernandez';

export default function App() {
  const [targetDate, setTargetDate] = useState('2026-08-30');
  const [playerCount, setPlayerCount] = useState(2);
  const [selectedCourse, setSelectedCourse] = useState('ALL');
  const [earliestTime, setEarliestTime] = useState('07:00');
  const [latestTime, setLatestTime] = useState('11:00');

  const [logs, setLogs] = useState([
    { type: 'info', text: '⛳ GOLF-AUTOBOOK SYSTEM // v1.2.0 initialized' },
    { type: 'accent', text: '🎯 Target Group: Wichita Municipal (ID: 8)' },
    { type: 'muted', text: 'Standing by for schedule trigger or direct API execution...' }
  ]);
  const [loading, setLoading] = useState(false);
  const logEndRef = useRef(null);

  const courseMap = {
    'ALL': [],
    'Auburn Hills': [8905],
    'MacDonald': [9001],
    'Tex Consolver': [9027],
    'Arthur B. Sim': [8903]
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs, loading]);

  const clearLogs = () => {
    setLogs([{ type: 'info', text: '⛳ Activity log reset.' }]);
  };

  const handleExecute = async (e) => {
    e.preventDefault();
    setLoading(true);

    const timeStamp = new Date().toLocaleTimeString();

    const payload = {
      targetDate,
      playerCount: parseInt(playerCount, 10),
      preferredCourses: courseMap[selectedCourse],
      timeWindow: { earliestTime, latestTime },
      memberProfileId: MEMBER_PROFILE_ID,
      email: MEMBER_EMAIL,
      name: MEMBER_NAME,
      golfClubGroupId: 8
    };

    setLogs(prev => [
      ...prev,
      { type: 'command', text: `[${timeStamp}] >> DISPATCH API -> ${targetDate} (${selectedCourse}) [${playerCount}P]` },
      { type: 'muted', text: `Payload: ${JSON.stringify(payload, null, 2)}` }
    ]);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      let data;
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (response.ok) {
        const isScheduled = typeof data === 'object' && data.status === 'scheduled';
        setLogs(prev => [
          ...prev,
          { 
            type: isScheduled ? 'accent' : 'success', 
            text: isScheduled 
              ? `[${response.status} OK] ⏰ AUTO-BOOKING SCHEDULED VIA AWS EVENTBRIDGE` 
              : `[${response.status} ${response.statusText || 'OK'}] API Gateway Response:` 
          },
          { type: 'muted', text: typeof data === 'object' ? JSON.stringify(data, null, 2) : data }
        ]);
      } else {
        setLogs(prev => [
          ...prev,
          { type: 'error', text: `[${response.status} ${response.statusText || 'ERROR'}] API Gateway Error:` },
          { type: 'error', text: typeof data === 'object' ? JSON.stringify(data, null, 2) : data }
        ]);
      }
    } catch (err) {
      setLogs(prev => [...prev, { type: 'error', text: `[ERR] Fetch Failed: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-pixel-grid text-gruvbox-fg p-3 sm:p-6 flex flex-col justify-center items-center font-pixelify">

      {/* Main Vintage Window Container */}
      <div className="w-full max-w-5xl bg-gruvbox-bg1 border-4 border-gruvbox-bg4 shadow-2xl overflow-hidden">

        {/* Macintosh Classic Window Header with Pixel Golfer Title */}
        <div className="bg-gruvbox-bg2 px-4 py-2.5 border-b-4 border-gruvbox-bg4 flex flex-wrap justify-between items-center gap-3 select-none">
          <div className="flex items-center space-x-3">

            {/* Header Title with Golfer Swing Image */}
            <div className="flex items-center space-x-2 pl-2">
              <img
                src="/pixel_golfer.jpg"
                alt="Golfer Swing Icon"
                className="w-7 h-7 object-cover border border-gruvbox-yellow"
              />
              <h1 className="font-pixel text-xs sm:text-sm font-bold tracking-wide text-gruvbox-yellow uppercase">
                GOLF-AUTOBOOK <span className="text-gruvbox-gray font-normal text-xs">// CONSOLE</span>
              </h1>
            </div>
          </div>

          <div className="flex items-center space-x-2 font-pixel text-[11px]">
            <span className="px-2.5 py-1 bg-gruvbox-bg0 text-gruvbox-aqua border border-gruvbox-bg4">
              MEMBER: {MEMBER_NAME}
            </span>
            <span className="px-2.5 py-1 bg-gruvbox-bg0 text-gruvbox-orange border border-gruvbox-bg4">
              ID: {MEMBER_PROFILE_ID}
            </span>
          </div>
        </div>

        {/* Vintage Macintosh Ruler Scale */}
        <div className="bg-gruvbox-bg0 text-gruvbox-dim px-4 py-1 border-b-2 border-gruvbox-bg3 font-vt text-sm overflow-x-auto select-none">
          |....T....|....1....|....T....|....2....|....T....|....3....|....T....|....4....|....T....|....5....|....T....|....6....|
        </div>

        {/* Main Grid: Form + Activity Log */}
        <div className="p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* AWS Booking Form */}
          <form onSubmit={handleExecute} className="lg:col-span-7 space-y-5 flex flex-col justify-between">

            {/* Booking Parameters Box */}
            <div className="pixel-box bg-gruvbox-bg1 p-4 space-y-4">
              <h2 className="text-xs font-pixel uppercase tracking-wider text-gruvbox-yellow font-bold border-b-2 border-gruvbox-bg3 pb-2">
                Booking Parameters
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-pixel text-gruvbox-gray mb-1">Target Date</label>
                  <input
                    type="date"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border-2 border-gruvbox-bg4 text-gruvbox-yellow px-3 py-2 text-sm font-pixel focus:outline-none focus:border-gruvbox-yellow"
                  />
                </div>

                <div>
                  <label className="block text-xs font-pixel text-gruvbox-gray mb-1">Target Course</label>
                  <select
                    value={selectedCourse}
                    onChange={(e) => setSelectedCourse(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border-2 border-gruvbox-bg4 text-gruvbox-yellow px-3 py-2 text-sm font-pixel focus:outline-none focus:border-gruvbox-yellow cursor-pointer"
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
                  <label className="block text-xs font-pixel text-gruvbox-gray mb-1">Player Count</label>
                  <select
                    value={playerCount}
                    onChange={(e) => setPlayerCount(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border-2 border-gruvbox-bg4 text-gruvbox-yellow px-3 py-2 text-sm font-pixel focus:outline-none focus:border-gruvbox-yellow cursor-pointer"
                  >
                    <option value={1}>1 Player</option>
                    <option value={2}>2 Players</option>
                    <option value={3}>3 Players</option>
                    <option value={4}>4 Players</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-pixel text-gruvbox-gray mb-1">Earliest Time</label>
                  <input
                    type="time"
                    value={earliestTime}
                    onChange={(e) => setEarliestTime(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border-2 border-gruvbox-bg4 text-gruvbox-yellow px-3 py-2 text-sm font-pixel focus:outline-none focus:border-gruvbox-yellow"
                  />
                </div>

                <div>
                  <label className="block text-xs font-pixel text-gruvbox-gray mb-1">Latest Time</label>
                  <input
                    type="time"
                    value={latestTime}
                    onChange={(e) => setLatestTime(e.target.value)}
                    className="w-full bg-gruvbox-bg0 border-2 border-gruvbox-bg4 text-gruvbox-yellow px-3 py-2 text-sm font-pixel focus:outline-none focus:border-gruvbox-yellow"
                  />
                </div>
              </div>
            </div>

            {/* Execute Button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-pixel-primary py-4 px-4 text-sm font-pixel tracking-wider uppercase disabled:opacity-50 cursor-pointer flex items-center justify-center space-x-2 transition-all shadow-md mt-4"
            >
              <span>⚡</span>
              <span>{loading ? 'Dispatching to AWS...' : 'Trigger Immediate Booking'}</span>
            </button>
          </form>

          {/* Activity Log / Output Stream */}
          <div className="lg:col-span-5 flex flex-col">
            <div className="flex-1 pixel-box bg-gruvbox-bg0 p-4 flex flex-col font-vt text-sm shadow-inner min-h-[320px]">

              <div className="flex justify-between items-center pb-2 mb-3 border-b-2 border-gruvbox-bg3 text-gruvbox-gray font-pixel text-xs">
                <span>// ACTIVITY LOG</span>
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={clearLogs}
                    className="px-2 py-0.5 bg-gruvbox-bg2 text-gruvbox-dim hover:text-gruvbox-yellow border border-gruvbox-bg4 text-[10px]"
                  >
                    CLEAR
                  </button>
                  <span className="text-gruvbox-aqua">● LIVE</span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 max-h-[340px] pr-2 text-base">
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
                  <div className="text-gruvbox-orange font-bold animate-pulse">
                    &gt;&gt; Dispatching request to AWS API Gateway...
                  </div>
                )}
                <div ref={logEndRef} />
              </div>

            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
