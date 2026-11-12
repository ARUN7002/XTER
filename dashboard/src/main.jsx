import React, { useReducer } from 'react';
import { createRoot } from 'react-dom/client';
import { dashboardReducer, deriveHealth, HealthLevel, initialDashboardState } from './dashboardState.js';
import './style.css';

function App() {
  const [state, dispatch] = useReducer(dashboardReducer, initialDashboardState);
  const health = deriveHealth(state);
  return <main className="shell">
    <header><div><p className="eyebrow">CONTROLLED AI ENGINEERING OPERATOR</p><h1>ANDREWS</h1></div><span className={`health health-${health.toLowerCase()}`}>{health}</span></header>
    <section className="notice">Dashboard controls are local UI state only. Guardian remains the independent authority.</section>
    <section className="grid">
      <article><h2>Session</h2><strong>{state.sessionStatus}</strong><p>Tasks: {state.completedTasks}/{state.totalTasks || '—'}</p><p>Current: {state.currentTask || 'None'}</p></article>
      <article><h2>Health</h2><p>Guardian: {state.guardian}</p><p>VM: {state.vm}</p><p>Qwen: {state.qwen}</p><p>Gemini: {state.gemini}</p></article>
      <article><h2>Controls</h2><div className="controls"><button onClick={() => dispatch({ type: 'SESSION_STARTED', totalTasks: 0 })}>Start</button><button onClick={() => dispatch({ type: 'PAUSE' })}>Pause</button><button onClick={() => dispatch({ type: 'RESUME' })}>Resume</button><button onClick={() => dispatch({ type: 'TAKE_CONTROL_REQUESTED' })}>Take Control</button><button onClick={() => dispatch({ type: 'TAKE_CONTROL_CONFIRMED' })}>Confirm Control</button><button className="danger" onClick={() => dispatch({ type: 'EMERGENCY_STOP_REQUESTED' })}>Emergency Stop</button></div></article>
    </section>
    <section className="status"><h2>Takeover status: {state.takeoverStatus}</h2><p>Automated input: {state.automationInputEnabled ? 'enabled' : 'disabled'}</p>{state.emergencyStopPending && <p className="warning">Emergency stop requested; Guardian confirmation is required.</p>}</section>
    <section className="status"><h2>Recent errors</h2>{state.recentErrors.length ? <ul>{state.recentErrors.map((error) => <li key={error}>{error}</li>)}</ul> : <p>None</p>}</section>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);

