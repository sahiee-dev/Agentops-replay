import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { apiService } from '../services/api';

const Compliance = () => {
    const { sessionId: urlSessionId } = useParams();
    const [sessions, setSessions] = useState([]);
    const [selectedSession, setSelectedSession] = useState(urlSessionId || '');
    const [complianceReport, setComplianceReport] = useState(null);
    const [flaggedSessions, setFlaggedSessions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [sessionDetails, setSessionDetails] = useState(null);

    useEffect(() => {
        fetchSessions();
        fetchFlaggedSessions();
    }, []);

    // Auto-analyze session from URL parameter
    useEffect(() => {
        if (urlSessionId && sessions.length > 0) {
            const sessionExists = sessions.find(s => s.id.toString() === urlSessionId);
            if (sessionExists) {
                setSelectedSession(urlSessionId);
                fetchComplianceReport(urlSessionId);
            }
        }
    }, [urlSessionId, sessions]);

    const fetchSessions = async () => {
        try {
            const response = await apiService.getSessions();
            setSessions(Array.isArray(response.data) ? response.data : []);
        } catch (error) {
            console.error('Error fetching sessions:', error);
            setSessions([]);
        }
    };

    // eslint-disable-next-line no-unused-vars
    const fetchSessionDetails = async (sessionId) => {
        try {
            const response = await apiService.getSession(sessionId);
            setSessionDetails(response.data);
        } catch (error) {
            console.error('Error fetching session details:', error);
        }
    };

    const fetchFlaggedSessions = async () => {
        try {
            const response = await apiService.getFlaggedSessions();
            const flaggedData = response.data;
            setFlaggedSessions(Array.isArray(flaggedData) ? flaggedData : []);
        } catch (error) {
            console.error('Error fetching flagged sessions:', error);
            setFlaggedSessions([]);
        }
    };

    const fetchComplianceReport = async (sessionId) => {
        setLoading(true);
        try {
            // Fetch both compliance report and session details
            const [complianceRes, sessionRes] = await Promise.all([
                apiService.getComplianceReport(sessionId),
                apiService.getSession(sessionId)
            ]);

            setComplianceReport(complianceRes.data);
            setSessionDetails(sessionRes.data);
            setLoading(false);
        } catch (error) {
            console.error('Error fetching compliance report:', error);

            // Create a mock compliance report based on session events
            try {
                const eventsRes = await apiService.getEvents({ session_id: sessionId });
                const events = eventsRes.data;
                const sessionRes = await apiService.getSession(sessionId);

                // Analyze events for compliance
                const flaggedEvents = events.filter(event =>
                    event.flags && event.flags.some(flag =>
                        ['high_cost', 'sensitive_data', 'external_api', 'security_violation'].includes(flag)
                    )
                );

                const mockReport = {
                    session_id: sessionId,
                    compliance_status: flaggedEvents.length > 0 ? 'non-compliant' : 'compliant',
                    risk_level: flaggedEvents.length > 2 ? 'high' : flaggedEvents.length > 0 ? 'medium' : 'low',
                    policy_violations: flaggedEvents.map(event =>
                        `${event.event_type} with flags: ${event.flags.join(', ')}`
                    ),
                    flagged_events_count: flaggedEvents.length,
                    total_events: events.length,
                    agent_name: sessionRes.data.agent_name,
                    status: sessionRes.data.status
                };

                setComplianceReport(mockReport);
                setSessionDetails(sessionRes.data);
            } catch (fallbackError) {
                console.error('Error creating fallback compliance report:', fallbackError);
            }

            setLoading(false);
        }
    };

    const handleSessionSelect = (sessionId) => {
        setSelectedSession(sessionId);
        if (sessionId) {
            fetchComplianceReport(sessionId);
        } else {
            setComplianceReport(null);
            setSessionDetails(null);
        }
    };

    const getRiskLevelColor = (riskLevel) => {
        switch (riskLevel?.toLowerCase()) {
            case 'high': return 'danger';
            case 'medium': return 'warning';
            case 'low': return 'success';
            default: return 'secondary';
        }
    };

    const getComplianceStatusColor = (status) => {
        switch (status?.toLowerCase()) {
            case 'compliant': return 'success';
            case 'non-compliant': return 'danger';
            case 'pending': return 'warning';
            default: return 'secondary';
        }
    };

    const safeFlaggedSessions = Array.isArray(flaggedSessions) ? flaggedSessions : [];
    const safeSessions = Array.isArray(sessions) ? sessions : [];

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h1>Compliance Reports</h1>
                    {sessionDetails && (
                        <p className="text-muted mb-0">
                            Analyzing: {sessionDetails.agent_name || 'Unknown Agent'}
                            <span className={`badge status-${sessionDetails.status} ms-2`}>
                                {sessionDetails.status}
                            </span>
                        </p>
                    )}
                </div>
                <button className="btn btn-outline-primary" onClick={fetchFlaggedSessions}>
                    <i className="bi bi-arrow-clockwise me-2"></i>
                    Refresh
                </button>
            </div>

            {/* Overview Cards */}
            <div className="row mb-4">
                <div className="col-md-4">
                    <div className="card status-card">
                        <div className="card-body text-center">
                            <i className="bi bi-shield-check text-success fs-1"></i>
                            <h3 className="mt-2">{safeSessions.length}</h3>
                            <p className="text-muted">Total Sessions</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-4">
                    <div className="card status-card">
                        <div className="card-body text-center">
                            <i className="bi bi-exclamation-triangle text-warning fs-1"></i>
                            <h3 className="mt-2">{safeFlaggedSessions.length}</h3>
                            <p className="text-muted">Flagged Sessions</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-4">
                    <div className="card status-card">
                        <div className="card-body text-center">
                            <i className="bi bi-check-circle text-info fs-1"></i>
                            <h3 className="mt-2">{Math.max(0, safeSessions.length - safeFlaggedSessions.length)}</h3>
                            <p className="text-muted">Clean Sessions</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Session Selection */}
            <div className="card mb-4">
                <div className="card-header">
                    <h5 className="mb-0">Generate Compliance Report</h5>
                </div>
                <div className="card-body">
                    <div className="row align-items-end">
                        <div className="col-md-8">
                            <label className="form-label">Select Session</label>
                            <select
                                className="form-control"
                                value={selectedSession}
                                onChange={(e) => handleSessionSelect(e.target.value)}
                            >
                                <option value="">Choose a session to analyze...</option>
                                {safeSessions.map(session => (
                                    <option key={session.id} value={session.id}>
                                        #{session.id} - {session.agent_name || 'Unknown'} ({session.status})
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="col-md-4">
                            {selectedSession && (
                                <button
                                    className="btn btn-primary w-100"
                                    onClick={() => fetchComplianceReport(selectedSession)}
                                    disabled={loading}
                                >
                                    {loading ? (
                                        <>
                                            <span className="spinner-border spinner-border-sm me-2"></span>
                                            Analyzing...
                                        </>
                                    ) : (
                                        <>
                                            <i className="bi bi-search me-2"></i>
                                            Re-analyze
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Compliance Report */}
            {complianceReport && (
                <div className="card mb-4">
                    <div className="card-header">
                        <h5 className="mb-0">
                            <i className="bi bi-clipboard-data me-2"></i>
                            Compliance Report - Session #{selectedSession}
                        </h5>
                    </div>
                    <div className="card-body">
                        <div className="row mb-3">
                            <div className="col-md-4">
                                <h6>Compliance Status</h6>
                                <span className={`badge bg-${getComplianceStatusColor(complianceReport.compliance_status)} fs-6`}>
                                    <i className="bi bi-shield-check me-1"></i>
                                    {complianceReport.compliance_status || 'Pending'}
                                </span>
                            </div>
                            <div className="col-md-4">
                                <h6>Risk Level</h6>
                                <span className={`badge bg-${getRiskLevelColor(complianceReport.risk_level)} fs-6`}>
                                    <i className="bi bi-exclamation-triangle me-1"></i>
                                    {complianceReport.risk_level || 'Unknown'}
                                </span>
                            </div>
                            <div className="col-md-4">
                                <h6>Events Summary</h6>
                                <span className="badge bg-info fs-6">
                                    <i className="bi bi-lightning me-1"></i>
                                    {complianceReport.flagged_events_count || 0} / {complianceReport.total_events || 0} flagged
                                </span>
                            </div>
                        </div>

                        {complianceReport.policy_violations && Array.isArray(complianceReport.policy_violations) && complianceReport.policy_violations.length > 0 && (
                            <div className="mt-3">
                                <h6>
                                    <i className="bi bi-exclamation-circle text-warning me-2"></i>
                                    Policy Violations
                                </h6>
                                <div className="alert alert-warning">
                                    <ul className="mb-0">
                                        {complianceReport.policy_violations.map((violation, index) => (
                                            <li key={index}>{violation}</li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        )}

                        <div className="mt-3">
                            <h6>Session Details</h6>
                            <div className="row">
                                <div className="col-md-6">
                                    <small className="text-muted">Agent:</small>
                                    <p>{complianceReport.agent_name || sessionDetails?.agent_name || 'Unknown'}</p>
                                </div>
                                <div className="col-md-6">
                                    <small className="text-muted">Status:</small>
                                    <p>
                                        <span className={`badge status-${complianceReport.status || sessionDetails?.status}`}>
                                            {complianceReport.status || sessionDetails?.status}
                                        </span>
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Flagged Sessions List */}
            <div className="card">
                <div className="card-header">
                    <h5 className="mb-0">
                        <i className="bi bi-flag me-2"></i>
                        Flagged Sessions ({safeFlaggedSessions.length})
                    </h5>
                </div>
                <div className="card-body">
                    {safeFlaggedSessions.length === 0 ? (
                        <div className="text-center py-4">
                            <i className="bi bi-shield-check fs-1 text-success"></i>
                            <p className="text-muted mt-2">No flagged sessions found</p>
                            <p className="text-muted">All sessions are compliant</p>
                        </div>
                    ) : (
                        <div className="table-responsive">
                            <table className="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Session ID</th>
                                        <th>Agent</th>
                                        <th>Status</th>
                                        <th>Risk Level</th>
                                        <th>Started At</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {safeFlaggedSessions.map(session => (
                                        <tr key={session.id}>
                                            <td>
                                                <strong>#{session.id}</strong>
                                            </td>
                                            <td>{session.agent_name || 'Unknown'}</td>
                                            <td>
                                                <span className={`badge status-${session.status}`}>
                                                    {session.status}
                                                </span>
                                            </td>
                                            <td>
                                                <span className={`badge bg-${getRiskLevelColor(session.risk_level)}`}>
                                                    {session.risk_level || 'Unknown'}
                                                </span>
                                            </td>
                                            <td>
                                                {new Date(session.started_at).toLocaleString()}
                                            </td>
                                            <td>
                                                <button
                                                    className="btn btn-sm btn-outline-primary"
                                                    onClick={() => handleSessionSelect(session.id)}
                                                >
                                                    <i className="bi bi-search"></i> Analyze
                                                </button>
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

export default Compliance;
