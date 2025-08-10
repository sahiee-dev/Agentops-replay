import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';

const Dashboard = () => {
    const [stats, setStats] = useState({
        totalSessions: 0,
        activeSessions: 0,
        totalEvents: 0,
        flaggedSessions: 0
    });
    const [recentSessions, setRecentSessions] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        try {
            const [sessionsRes, eventsRes] = await Promise.all([
                apiService.getSessions(),
                apiService.getEvents()
            ]);

            const sessions = sessionsRes.data;
            const events = eventsRes.data;

            setStats({
                totalSessions: sessions.length,
                activeSessions: sessions.filter(s => s.status === 'running').length,
                totalEvents: events.length,
                flaggedSessions: sessions.filter(s => s.status === 'failed').length
            });

            setRecentSessions(sessions.slice(0, 5));
            setLoading(false);
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="loading">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-2">Loading dashboard...</p>
            </div>
        );
    }

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h1>Dashboard</h1>
                <button className="btn btn-primary" onClick={fetchDashboardData}>
                    <i className="bi bi-arrow-clockwise me-2"></i>
                    Refresh
                </button>
            </div>

            {/* Stats Cards */}
            <div className="row mb-4">
                <div className="col-md-3">
                    <div className="card status-card">
                        <div className="card-body text-center">
                            <i className="bi bi-list-task text-primary fs-1"></i>
                            <h3 className="mt-2">{stats.totalSessions}</h3>
                            <p className="text-muted">Total Sessions</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-3">
                    <div className="card status-card">
                        <div className="card-body text-center">
                            <i className="bi bi-play-circle text-success fs-1"></i>
                            <h3 className="mt-2">{stats.activeSessions}</h3>
                            <p className="text-muted">Active Sessions</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-3">
                    <div className="card status-card">
                        <div className="card-body text-center">
                            <i className="bi bi-lightning text-warning fs-1"></i>
                            <h3 className="mt-2">{stats.totalEvents}</h3>
                            <p className="text-muted">Total Events</p>
                        </div>
                    </div>
                </div>
                <div className="col-md-3">
                    <div className="card status-card">
                        <div className="card-body text-center">
                            <i className="bi bi-exclamation-triangle text-danger fs-1"></i>
                            <h3 className="mt-2">{stats.flaggedSessions}</h3>
                            <p className="text-muted">Flagged Sessions</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Recent Sessions */}
            <div className="card">
                <div className="card-header">
                    <h5 className="mb-0">Recent Sessions</h5>
                </div>
                <div className="card-body">
                    {recentSessions.length === 0 ? (
                        <p className="text-muted">No sessions found</p>
                    ) : (
                        <div className="table-responsive">
                            <table className="table table-hover">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Agent</th>
                                        <th>Status</th>
                                        <th>Started</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {recentSessions.map(session => (
                                        <tr key={session.id}>
                                            <td>#{session.id}</td>
                                            <td>{session.agent_name || 'Unknown'}</td>
                                            <td>
                                                <span className={`badge status-${session.status}`}>
                                                    {session.status}
                                                </span>
                                            </td>
                                            <td>
                                                {new Date(session.started_at).toLocaleString()}
                                            </td>
                                            <td>
                                                <button className="btn btn-sm btn-outline-primary me-2">
                                                    <i className="bi bi-eye"></i>
                                                </button>
                                                <button className="btn btn-sm btn-outline-secondary">
                                                    <i className="bi bi-play"></i>
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

export default Dashboard;
