import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// API service methods
export const apiService = {
  // Sessions
  getSessions: () => api.get('/sessions/'),
  createSession: (data) => api.post('/sessions/', data),
  getSession: (id) => api.get(`/sessions/${id}`),
  
  // Events
  getEvents: (params = {}) => api.get('/events/', { params }),
  createEvent: (data) => api.post('/events/', data),
  getEvent: (id) => api.get(`/events/${id}`),
  
  // Replay
  getReplayOverview: () => api.get('/replay/'),
  replaySession: (id) => api.get(`/replay/${id}`),
  
  // Compliance
  getComplianceOverview: () => api.get('/compliance/'),
  getComplianceReport: (id) => api.get(`/compliance/${id}`),
  getFlaggedSessions: () => api.get('/compliance/sessions/flagged'),

  //Generate Events
  generateEvents: (data) => api.post('/event-generation/generate', data),
  getEventScenarios: () => api.get('/event-generation/scenarios'),

  // Live Agent API
  startAgentSession: () => api.post('/live-agent/start-agent-session'),
  chatWithAgent: (data) => api.post('/live-agent/chat', data),
  endAgentSession: (sessionId) => api.post(`/live-agent/end-agent-session/${sessionId}`),
};

export default api;
