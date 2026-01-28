import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { apiService } from '../services/api';

const Replay = () => {
    const { sessionId: urlSessionId } = useParams();
    const [sessions, setSessions] = useState([]);
    const [selectedSession, setSelectedSession] = useState(urlSessionId || '');
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(false);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentEventIndex, setCurrentEventIndex] = useState(0);
    const [sessionDetails, setSessionDetails] = useState(null);
    const replayIntervalRef = useRef(null);  // Store interval ID
    const eventsRef = useRef(events);  // Track current events to prevent stale closure

    // Keep eventsRef in sync with events state
    useEffect(() => {
        eventsRef.current = events;
    }, [events]);

    useEffect(() => {
        fetchSessions();
    }, []);

    useEffect(() => {
        if (selectedSession) {
            fetchSessionEvents(selectedSession);
            fetchSessionDetails(selectedSession);
        }
    }, [selectedSession]);

    // Auto-set session from URL parameter
    useEffect(() => {
        if (urlSessionId && sessions.length > 0) {
            const sessionExists = sessions.find(s => s.id.toString() === urlSessionId);
            if (sessionExists) {
                setSelectedSession(urlSessionId);
            }
        }
    }, [urlSessionId, sessions]);

    const fetchSessions = async () => {
        try {
            const response = await apiService.getSessions();
            setSessions(response.data);
        } catch (error) {
            console.error('Error fetching sessions:', error);
        }
    };

    const fetchSessionDetails = async (sessionId) => {
        try {
            const response = await apiService.getSession(sessionId);
            setSessionDetails(response.data);
        } catch (error) {
            console.error('Error fetching session details:', error);
        }
    };

    const fetchSessionEvents = async (sessionId) => {
        setLoading(true);
        try {
            const response = await apiService.getEvents({ session_id: sessionId });
            setEvents(response.data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)));
            setCurrentEventIndex(0);
            setLoading(false);
        } catch (error) {
            console.error('Error fetching events:', error);
            setLoading(false);
        }
    };

    const startReplay = () => {
        setIsPlaying(true);
        setCurrentEventIndex(0);

        const interval = setInterval(() => {
            setCurrentEventIndex(prevIndex => {
                // Use eventsRef to get current events (prevent stale closure)
                if (prevIndex >= eventsRef.current.length - 1) {
                    setIsPlaying(false);
                    clearInterval(interval);
                    replayIntervalRef.current = null;
                    return prevIndex;
                }
                return prevIndex + 1;
            });
        }, 1000); // 1 second between events

        replayIntervalRef.current = interval;  // Store interval ID
    };

    const stopReplay = () => {
        if (replayIntervalRef.current) {
            clearInterval(replayIntervalRef.current);
            replayIntervalRef.current = null;
        }
        setIsPlaying(false);
    };

    const resetReplay = () => {
        if (replayIntervalRef.current) {
            clearInterval(replayIntervalRef.current);
            replayIntervalRef.current = null;
        }
        setIsPlaying(false);
        setCurrentEventIndex(0);
    };

    // Cleanup interval on unmount
    useEffect(() => {
        return () => {
            if (replayIntervalRef.current) {
                clearInterval(replayIntervalRef.current);
            }
        };
    }, []);

    const EventItem = ({ event, index, isActive, isCompleted }) => (
        <div className={`event-item ${isActive ? 'border-primary' : ''} ${isCompleted ? 'opacity-50' : ''}`}>
            <div className="d-flex justify-content-between align-items-start">
                <div className="flex-grow-1">
                    <div className="d-flex align-items-center mb-2">
                        {isCompleted && <i className="bi bi-check-circle-fill text-success me-2"></i>}
                        {isActive && <i className="bi bi-play-circle-fill text-primary me-2"></i>}
                        {!isCompleted && !isActive && <i className="bi bi-circle text-muted me-2"></i>}
                        <h6 className="mb-0">{event.event_type}</h6>
                        <span className="badge bg-secondary ms-2">#{index + 1}</span>
                    </div>
                    {event.tool_name && (
                        <p className="text-muted mb-1">
                            <i className="bi bi-tools me-1"></i>
                            Tool: {event.tool_name}
                        </p>
                    )}
                    {event.flags && event.flags.length > 0 && (
                        <div className="mb-1">
                            {event.flags.map(flag => (
                                <span key={flag} className="badge bg-warning text-dark me-1">
                                    {flag}
                                </span>
                            ))}
                        </div>
                    )}
                    <small className="event-timestamp">
                        {new Date(event.timestamp).toLocaleString()}
                    </small>
                </div>
            </div>
        </div>
    );

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h1>Session Replay</h1>
                    {sessionDetails && (
                        <p className="text-muted mb-0">
                            Replaying: {sessionDetails.agent_name || 'Unknown Agent'}
                            <span className={`badge status-${sessionDetails.status} ms-2`}>
                                {sessionDetails.status}
                            </span>
                        </p>
                    )}
                </div>
                <div className="d-flex gap-2">
                    {selectedSession && (
                        <>
                            <button
                                className="btn btn-success"
                                onClick={startReplay}
                                disabled={isPlaying || events.length === 0}
                            >
                                <i className="bi bi-play me-2"></i>
                                Start Replay
                            </button>
                            <button
                                className="btn btn-warning"
                                onClick={resetReplay}
                                disabled={isPlaying || currentEventIndex === 0}
                            >
                                <i className="bi bi-arrow-counterclockwise me-2"></i>
                                Reset
                            </button>
                            <button
                                className="btn btn-danger"
                                onClick={stopReplay}
                                disabled={!isPlaying}
                            >
                                <i className="bi bi-stop me-2"></i>
                                Stop
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Session Selection */}
            <div className="card mb-4">
                <div className="card-body">
                    <div className="row align-items-end">
                        <div className="col-md-8">
                            <label className="form-label">Select Session to Replay</label>
                            <select
                                className="form-control"
                                value={selectedSession}
                                onChange={(e) => setSelectedSession(e.target.value)}
                            >
                                <option value="">Choose a session...</option>
                                {sessions.map(session => (
                                    <option key={session.id} value={session.id}>
                                        #{session.id} - {session.agent_name || 'Unknown'} ({session.status})
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="col-md-4">
                            {selectedSession && (
                                <div className="text-muted">
                                    <i className="bi bi-lightning me-1"></i>
                                    {events.length} events found
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Replay Progress */}
            {selectedSession && events.length > 0 && (
                <div className="card mb-4">
                    <div className="card-body">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                            <span>
                                <i className="bi bi-clock-history me-2"></i>
                                Replay Progress
                            </span>
                            <span className="badge bg-primary">
                                {currentEventIndex + 1} / {events.length}
                            </span>
                        </div>
                        <div className="progress" style={{ height: '8px' }}>
                            <div
                                className="progress-bar bg-primary"
                                style={{ width: `${((currentEventIndex + 1) / events.length) * 100}%` }}
                            ></div>
                        </div>
                        <div className="d-flex justify-content-between mt-1">
                            <small className="text-muted">
                                {events.length > 0 ? new Date(events[0].timestamp).toLocaleString() : ''}
                            </small>
                            <small className="text-muted">
                                {events.length > 0 ? new Date(events[events.length - 1].timestamp).toLocaleString() : ''}
                            </small>
                        </div>
                    </div>
                </div>
            )}

            {/* Events Timeline */}
            {loading ? (
                <div className="loading">
                    <div className="spinner-border text-primary" role="status">
                        <span className="visually-hidden">Loading...</span>
                    </div>
                    <p className="mt-2">Loading session events...</p>
                </div>
            ) : selectedSession && events.length > 0 ? (
                <div className="replay-container">
                    <h5 className="mb-3">
                        <i className="bi bi-collection-play me-2"></i>
                        Session Events Timeline
                    </h5>
                    {events.map((event, index) => (
                        <EventItem
                            key={event.id}
                            event={event}
                            index={index}
                            isActive={isPlaying && index === currentEventIndex}
                            isCompleted={index < currentEventIndex}
                        />
                    ))}
                </div>
            ) : selectedSession ? (
                <div className="text-center py-4">
                    <i className="bi bi-inbox fs-1 text-muted"></i>
                    <p className="text-muted mt-2">No events found for this session</p>
                    <p className="text-muted">Try adding some events to see the replay in action</p>
                </div>
            ) : (
                <div className="text-center py-4">
                    <i className="bi bi-play-circle fs-1 text-muted"></i>
                    <p className="text-muted mt-2">Select a session to start replay</p>
                </div>
            )}
        </div>
    );
};

export default Replay;
