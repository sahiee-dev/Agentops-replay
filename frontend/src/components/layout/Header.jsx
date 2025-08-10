import React, { forwardRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const Header = forwardRef(({ sidebarCollapsed, onToggleSidebar }, ref) => {
    const location = useLocation();
    const navigate = useNavigate();
    const [showUserMenu, setShowUserMenu] = useState(false);

    const getPageTitle = () => {
        switch (location.pathname) {
            case '/': return 'Dashboard';
            case '/sessions': return 'Sessions';
            case '/replay': return 'Replay';
            case '/compliance': return 'Compliance';
            case '/live-agent': return 'Live Agent';
            default:
                if (location.pathname.startsWith('/replay/')) return 'Session Replay';
                if (location.pathname.startsWith('/compliance/')) return 'Compliance Analysis';
                return 'AgentOps Replay';
        }
    };

    const getPageIcon = () => {
        switch (location.pathname) {
            case '/': return 'bi-speedometer2';
            case '/sessions': return 'bi-list-task';
            case '/replay': return 'bi-play-circle';
            case '/compliance': return 'bi-shield-check';
            case '/live-agent': return 'bi-robot';
            default: return 'bi-house-door';
        }
    };

    return (
        <header ref={ref} className="modern-header">
            <div className="header-container">
                {/* Left Section */}
                <div className="header-left">
                    <button
                        className="sidebar-toggle-btn"
                        onClick={onToggleSidebar}
                        aria-label="Toggle Sidebar"
                        title={sidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
                    >
                        <i className={`bi bi-${sidebarCollapsed ? 'list' : 'x-lg'}`}></i>
                    </button>

                    <div className="header-brand">
                        <div className="brand-logo">
                            <i className="bi bi-robot brand-icon"></i>
                            <div className="brand-text">
                                <h1 className="brand-title">AgentOps</h1>
                                <span className="brand-subtitle">Replay</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Center Section - Page Info */}
                <div className="header-center">
                    <div className="page-indicator">
                        <div className="page-icon">
                            <i className={`bi ${getPageIcon()}`}></i>
                        </div>
                        <div className="page-info">
                            <h2 className="page-title">{getPageTitle()}</h2>
                            <span className="page-subtitle">AI Agent Monitoring</span>
                        </div>
                    </div>
                </div>

                {/* Right Section */}
                <div className="header-right">
                    {/* Quick Actions */}
                    <div className="quick-actions">
                        <button
                            className="action-btn"
                            onClick={() => navigate('/sessions')}
                            title="New Session"
                        >
                            <i className="bi bi-plus-circle"></i>
                        </button>
                        <button
                            className="action-btn"
                            onClick={() => navigate('/live-agent')}
                            title="Live Agent"
                        >
                            <i className="bi bi-robot"></i>
                        </button>
                        <button
                            className="action-btn notification-btn"
                            title="Notifications"
                        >
                            <i className="bi bi-bell"></i>
                            <span className="notification-badge">3</span>
                        </button>
                    </div>

                    {/* System Status */}
                    <div className="system-status">
                        <div className="status-indicator online">
                            <div className="status-dot"></div>
                            <span className="status-text">System Online</span>
                        </div>
                    </div>

                    {/* User Menu */}
                    <div className="user-menu-container">
                        <button
                            className="user-menu-trigger"
                            onClick={() => setShowUserMenu(!showUserMenu)}
                            onBlur={() => setTimeout(() => setShowUserMenu(false), 150)}
                        >
                            <div className="user-avatar">
                                <i className="bi bi-person-circle"></i>
                            </div>
                            <div className="user-info">
                                <span className="user-name">Admin User</span>
                                <small className="user-role">System Administrator</small>
                            </div>
                            <i className="bi bi-chevron-down dropdown-arrow"></i>
                        </button>

                        {showUserMenu && (
                            <div className="user-dropdown">
                                <div className="dropdown-item">
                                    <i className="bi bi-person"></i>
                                    Profile
                                </div>
                                <div className="dropdown-item">
                                    <i className="bi bi-gear"></i>
                                    Settings
                                </div>
                                <div className="dropdown-divider"></div>
                                <div className="dropdown-item logout">
                                    <i className="bi bi-box-arrow-right"></i>
                                    Logout
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </header>
    );
});

Header.displayName = 'Header';
export default Header;
