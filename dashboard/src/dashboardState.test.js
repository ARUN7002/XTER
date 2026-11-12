import test from 'node:test';
import assert from 'node:assert/strict';
import { dashboardReducer, deriveHealth, HealthLevel, initialDashboardState } from './dashboardState.js';

test('stale health is amber', () => {
  const state = { ...initialDashboardState, guardian: 'HEALTHY', vm: 'READY', qwen: 'READY', lastHealthUpdate: 1000 };
  assert.equal(deriveHealth(state, 40001), HealthLevel.AMBER);
});

test('security failures are red', () => {
  const state = { ...initialDashboardState, guardian: 'STOPPED', lastHealthUpdate: Date.now() };
  assert.equal(deriveHealth(state), HealthLevel.RED);
});

test('healthy current services are green', () => {
  const state = { ...initialDashboardState, guardian: 'HEALTHY', vm: 'READY', qwen: 'READY', lastHealthUpdate: 1000 };
  assert.equal(deriveHealth(state, 2000), HealthLevel.GREEN);
});

test('take control revokes automated input before confirmation', () => {
  const pending = dashboardReducer({ ...initialDashboardState, automationInputEnabled: true }, { type: 'TAKE_CONTROL_REQUESTED' });
  assert.equal(pending.automationInputEnabled, false);
  assert.equal(pending.takeoverStatus, 'REVOCATION_PENDING');
  assert.equal(dashboardReducer(pending, { type: 'TAKE_CONTROL_CONFIRMED' }).takeoverStatus, 'MANUAL_CONTROL');
});

test('take control cannot be confirmed while input remains enabled', () => {
  const pending = { ...initialDashboardState, takeoverStatus: 'REVOCATION_PENDING', automationInputEnabled: true };
  assert.equal(dashboardReducer(pending, { type: 'TAKE_CONTROL_CONFIRMED' }).takeoverStatus, 'REVOCATION_PENDING');
});

test('emergency stop is available without a dashboard session', () => {
  const stopped = dashboardReducer(initialDashboardState, { type: 'EMERGENCY_STOP_REQUESTED' });
  assert.equal(stopped.sessionStatus, 'SECURITY_STOPPED');
  assert.equal(stopped.automationInputEnabled, false);
});

test('dashboard disconnect does not alter Guardian state', () => {
  const state = { ...initialDashboardState, guardian: 'HEALTHY' };
  assert.equal(dashboardReducer(state, { type: 'DASHBOARD_DISCONNECTED' }).guardian, 'HEALTHY');
});

test('resume is blocked during manual control', () => {
  const state = { ...initialDashboardState, sessionStatus: 'PAUSED', takeoverStatus: 'MANUAL_CONTROL' };
  assert.equal(dashboardReducer(state, { type: 'RESUME' }).sessionStatus, 'PAUSED');
});

test('errors are bounded and newest first', () => {
  let state = initialDashboardState;
  for (let i = 0; i < 7; i += 1) state = dashboardReducer(state, { type: 'ERROR', message: `E${i}` });
  assert.deepEqual(state.recentErrors, ['E6', 'E5', 'E4', 'E3', 'E2']);
});

