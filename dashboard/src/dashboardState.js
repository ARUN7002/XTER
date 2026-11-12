export const HealthLevel = Object.freeze({ GREEN: 'GREEN', AMBER: 'AMBER', RED: 'RED' });

export const initialDashboardState = Object.freeze({
  sessionStatus: 'IDLE',
  currentTask: null,
  completedTasks: 0,
  totalTasks: 0,
  guardian: 'HEALTHY',
  vm: 'UNKNOWN',
  qwen: 'UNAVAILABLE',
  gemini: 'MANUAL',
  automationInputEnabled: false,
  takeoverStatus: 'NONE',
  emergencyStopPending: false,
  lastHealthUpdate: null,
  recentErrors: [],
});

export function deriveHealth(state, now = Date.now(), staleAfterMs = 30000) {
  if (state.guardian === 'STOPPED' || state.sessionStatus === 'SECURITY_STOPPED') return HealthLevel.RED;
  if (state.guardian !== 'HEALTHY' || state.vm === 'CRASHED') return HealthLevel.RED;
  if (!state.lastHealthUpdate || now - state.lastHealthUpdate > staleAfterMs) return HealthLevel.AMBER;
  if (state.qwen === 'UNAVAILABLE' || state.vm === 'UNKNOWN') return HealthLevel.AMBER;
  return HealthLevel.GREEN;
}

export function dashboardReducer(state, event) {
  switch (event.type) {
    case 'HEALTH_UPDATE':
      return { ...state, ...event.payload, lastHealthUpdate: event.now ?? Date.now() };
    case 'SESSION_STARTED':
      return { ...state, sessionStatus: 'RUNNING', totalTasks: event.totalTasks, completedTasks: 0 };
    case 'PAUSE':
      return { ...state, sessionStatus: 'PAUSED' };
    case 'RESUME':
      return state.takeoverStatus === 'NONE' && state.guardian === 'HEALTHY'
        ? { ...state, sessionStatus: 'RUNNING' }
        : state;
    case 'TAKE_CONTROL_REQUESTED':
      return { ...state, takeoverStatus: 'REVOCATION_PENDING', automationInputEnabled: false, sessionStatus: 'PAUSED' };
    case 'TAKE_CONTROL_CONFIRMED':
      return state.takeoverStatus === 'REVOCATION_PENDING' && !state.automationInputEnabled
        ? { ...state, takeoverStatus: 'MANUAL_CONTROL' }
        : state;
    case 'EMERGENCY_STOP_REQUESTED':
      return { ...state, emergencyStopPending: true, sessionStatus: 'SECURITY_STOPPED', automationInputEnabled: false };
    case 'EMERGENCY_STOP_CONFIRMED':
      return { ...state, emergencyStopPending: false, sessionStatus: 'STOPPED', guardian: 'STOPPED', automationInputEnabled: false };
    case 'ERROR':
      return { ...state, recentErrors: [event.message, ...state.recentErrors].slice(0, 5) };
    default:
      return state;
  }
}

