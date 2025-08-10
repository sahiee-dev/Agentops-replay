import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import QuickEventGenerator from '../components/events/QuickEventGenerator';

const Sessions = () => {
    const navigate = useNavigate();
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [selectedSession, setSelectedSession] = useState(null);
    const [showDetails, setShowDetails] = useState(false);
    const [showEventGenerator, setShowEventGenerator] = useState(false);
    const [eventGeneratorSession, setEventGeneratorSession] = useState(null);
    const [newSession, setNewSession] = useState({
        user_id: 2, // Using the user ID that exists in your database
        agent_name: '',
        status: 'running'
    });

    useEffect(() => {
        fetchSessions();
    }, []);

    const fetchSessions = async () => {
        try {
            const response = await apiService.getSessions();
            setSessions(response.data);
            setLoading(false);
        } catch (error) {
            console.error('Error fetching sessions:', error);
            setLoading(false);
        }
    };

    const handleCreateSession = async (e) => {
        e.preventDefault();
        try {
            await apiService.createSession(newSession);
            setNewSession({ user_id: 2, agent_name: '', status: 'running' });
            setShowCreateForm(false);
            fetchSessions(); // Refresh the list
        } catch (error) {
            console.error('Error creating session:', error);
        }
    };

    const handleInputChange = (e) => {
        setNewSession({
            ...newSession,
            [e.target.name]: e.target.value
        });
    };

    // Action handlers for the buttons
    const handleViewSession = async (session) => {
        try {
            const response = await apiService.getSession(session.id);
            setSelectedSession(response.data);
            setShowDetails(true);
        } catch (error) {
            console.error('Error fetching session details:', error);
        }
    };

    const handleReplaySession = (sessionId) => {
        navigate(`/replay/${sessionId}`);
    };

    const handleComplianceCheck = (sessionId) => {
        navigate(`/compliance/${sessionId}`);
    };

    const handleGenerateEvents = (sessionId) => {
        setEventGeneratorSession(sessionId);
        setShowEventGenerator(true);
    };

    const handleEventsGenerated = () => {
        fetchSessions(); // Refresh sessions to show updated data
        setShowEventGenerator(false);
    };

    if (loading) {
        return (
            <div className="loading">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-2">Loading sessions...</p>
            </div>
        );
    }

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h1>Sessions</h1>
                <div className="d-flex gap-2">
                    <button
                        className="btn btn-outline-success"
                        onClick={() => setShowEventGenerator(!showEventGenerator)}
                        disabled={sessions.length === 0}
                    >
                        <i className="bi bi-magic me-2"></i>
                        Event Generator
                    </button>
                    <button
                        className="btn btn-primary"
                        onClick={() => setShowCreateForm(!showCreateForm)}
                    >
                        <i className="bi bi-plus-circle me-2"></i>
                        New Session
                    </button>
                </div>
            </div>

            {/* Event Generator Component */}
            {showEventGenerator && sessions.length > 0 && (
                <div className="mb-4">
                    <QuickEventGenerator
                        sessionId={eventGeneratorSession || sessions[0].id}
                        onEventsGenerated={handleEventsGenerated}
                    />
                    <div className="text-center mt-3">
                        <button
                            className="btn btn-sm btn-outline-secondary"
                            onClick={() => setShowEventGenerator(false)}
                        >
                            Hide Event Generator
                        </button>
                    </div>
                </div>
            )}

            {/* Session Details Modal */}
            {showDetails && selectedSession && (
                <div className="modal show d-block" tabIndex="-1">
                    <div className="modal-dialog modal-lg">
                        <div className="modal-content">
                            <div className="modal-header">
                                <h5 className="modal-title">Session Details - #{selectedSession.id}</h5>
                                <button
                                    type="button"
                                    className="btn-close"
                                    onClick={() => setShowDetails(false)}
                                ></button>
                            </div>
                            <div className="modal-body">
                                <div className="row">
                                    <div className="col-md-6">
                                        <h6>Basic Information</h6>
                                        <table className="table table-sm">
                                            <tbody>
                                                <tr>
                                                    <td><strong>Session ID:</strong></td>
                                                    <td>#{selectedSession.id}</td>
                                                </tr>
                                                <tr>
                                                    <td><strong>Agent Name:</strong></td>
                                                    <td>{selectedSession.agent_name || 'Unknown'}</td>
                                                </tr>
                                                <tr>
                                                    <td><strong>Status:</strong></td>
                                                    <td>
                                                        <span className={`badge status-${selectedSession.status}`}>
                                                            {selectedSession.status}
                                                        </span>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td><strong>User ID:</strong></td>
                                                    <td>{selectedSession.user_id}</td>
                                                </tr>
                                                <tr>
                                                    <td><strong>Started At:</strong></td>
                                                    <td>{new Date(selectedSession.started_at).toLocaleString()}</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                    <div className="col-md-6">
                                        <h6>Quick Actions</h6>
                                        <div className="d-flex flex-column gap-2">
                                            <button
                                                className="btn btn-success"
                                                onClick={() => handleGenerateEvents(selectedSession.id)}
                                            >
                                                <i className="bi bi-magic me-2"></i>
                                                Generate Events
                                            </button>
                                            <button
                                                className="btn btn-primary"
                                                onClick={() => {
                                                    setShowDetails(false);
                                                    handleReplaySession(selectedSession.id);
                                                }}
                                            >
                                                <i className="bi bi-play me-2"></i>
                                                Replay Session
                                            </button>
                                            <button
                                                className="btn btn-info"
                                                onClick={() => {
                                                    setShowDetails(false);
                                                    handleComplianceCheck(selectedSession.id);
                                                }}
                                            >
                                                <i className="bi bi-shield-check me-2"></i>
                                                Compliance Report
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="modal-footer">
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setShowDetails(false)}
                                >
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Session Form */}
            {showCreateForm && (
                <div className="card mb-4">
                    <div className="card-header">
                        <h5 className="mb-0">Create New Session</h5>
                    </div>
                    <div className="card-body">
                        <form onSubmit={handleCreateSession}>
                            <div className="row">
                                <div className="col-md-6">
                                    <div className="mb-3">
                                        <label className="form-label">Agent Name</label>
                                        <input
                                            type="text"
                                            className="form-control"
                                            name="agent_name"
                                            value={newSession.agent_name}
                                            onChange={handleInputChange}
                                            placeholder="Enter agent name"
                                            required
                                        />
                                    </div>
                                </div>
                                <div className="col-md-6">
                                    <div className="mb-3">
                                        <label className="form-label">Status</label>
                                        <select
                                            className="form-control"
                                            name="status"
                                            value={newSession.status}
                                            onChange={handleInputChange}
                                        >
                                            <option value="running">Running</option>
                                            <option value="completed">Completed</option>
                                            <option value="failed">Failed</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            <div className="d-flex gap-2">
                                <button type="submit" className="btn btn-primary">
                                    Create Session
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setShowCreateForm(false)}
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Sessions List */}
            <div className="card">
                <div className="card-header">
                    <h5 className="mb-0">All Sessions ({sessions.length})</h5>
                </div>
                <div className="card-body">
                    {sessions.length === 0 ? (
                        <div className="text-center py-4">
                            <i className="bi bi-inbox fs-1 text-muted"></i>
                            <p className="text-muted mt-2">No sessions found</p>
                            <button
                                className="btn btn-primary"
                                onClick={() => setShowCreateForm(true)}
                            >
                                Create Your First Session
                            </button>
                        </div>
                    ) : (
                        <div className="table-responsive">
                            <table className="table table-hover">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Agent Name</th>
                                        <th>Status</th>
                                        <th>User ID</th>
                                        <th>Started At</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {sessions.map(session => (
                                        <tr key={session.id}>
                                            <td>
                                                <strong>#{session.id}</strong>
                                            </td>
                                            <td>{session.agent_name || 'Unknown Agent'}</td>
                                            <td>
                                                <span className={`badge status-${session.status}`}>
                                                    {session.status}
                                                </span>
                                            </td>
                                            <td>{session.user_id}</td>
                                            <td>
                                                {new Date(session.started_at).toLocaleString()}
                                            </td>
                                            <td>
                                                <div className="btn-group" role="group">
                                                    <button
                                                        className="btn btn-sm btn-outline-primary"
                                                        onClick={() => handleViewSession(session)}
                                                        title="View Session Details"
                                                    >
                                                        <i className="bi bi-eye"></i>
                                                    </button>
                                                    <button
                                                        className="btn btn-sm btn-outline-success"
                                                        onClick={() => handleGenerateEvents(session.id)}
                                                        title="Generate Events"
                                                    >
                                                        <i className="bi bi-magic"></i>
                                                    </button>
                                                    <button
                                                        className="btn btn-sm btn-outline-secondary"
                                                        onClick={() => handleReplaySession(session.id)}
                                                        title="Replay Session"
                                                    >
                                                        <i className="bi bi-play"></i>
                                                    </button>
                                                    <button
                                                        className="btn btn-sm btn-outline-info"
                                                        onClick={() => handleComplianceCheck(session.id)}
                                                        title="Compliance Report"
                                                    >
                                                        <i className="bi bi-shield-check"></i>
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Sessions;
