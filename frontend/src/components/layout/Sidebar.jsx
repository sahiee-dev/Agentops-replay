/* eslint-disable no-unused-vars */
import React, { forwardRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const Sidebar = forwardRef(({ collapsed, onToggle }, ref) => {
    const location = useLocation();
    const [hoveredItem, setHoveredItem] = useState(null);

    const navigation = [
        {
            name: 'Dashboard',
            href: '/',
            icon: 'bi-speedometer2',
            description: 'Overview & Analytics',
            badge: null
        },
        {
            name: 'Sessions',
            href: '/sessions',
            icon: 'bi-list-task',
            description: 'Manage Agent Sessions',
            badge: '5'
        },
        {
            name: 'Replay',
            href: '/replay',
            icon: 'bi-play-circle',
            description: 'Session Playback',
            badge: null
        },
        {
            name: 'Compliance',
            href: '/compliance',
            icon: 'bi-shield-check',
            description: 'Policy Monitoring',
            badge: 'New'
        },
        {
            name: 'Live Agent',
            href: '/live-agent',
            icon: 'bi-robot',
            description: 'AI Agent Demo',
            badge: null
        }
    ];

    const quickActions = [
        {
            name: 'Analytics',
            href: '/compliance',
            icon: 'bi-graph-up',
            description: 'Performance Metrics'
        }
    ];

    return (
        <nav ref={ref} className={`modern-sidebar ${collapsed ? 'collapsed' : 'expanded'}`}>
            <div className="sidebar-content">
                {/* Main Navigation */}
                <div className="nav-section">
                    <div className="nav-header">
                        {!collapsed && <h3>Navigation</h3>}
                    </div>
                    <ul className="nav-list main-nav">
                        {navigation.map((item) => {
                            const isActive = location.pathname === item.href ||
                                (item.href !== '/' && location.pathname.startsWith(item.href));

                            return (
                                <li key={item.name} className="nav-item">
                                    <NavLink
                                        to={item.href}
                                        className={`nav-link ${isActive ? 'active' : ''}`}
                                        onMouseEnter={() => setHoveredItem(item.name)}
                                        onMouseLeave={() => setHoveredItem(null)}
                                    >
                                        <div className="nav-link-content">
                                            <div className="nav-icon">
                                                <i className={`bi ${item.icon}`}></i>
                                            </div>

                                            {!collapsed && (
                                                <div className="nav-text">
                                                    <span className="nav-title">{item.name}</span>
                                                    <small className="nav-description">{item.description}</small>
                                                </div>
                                            )}

                                            {item.badge && !collapsed && (
                                                <span className={`nav-badge ${item.badge === 'New' ? 'badge-new' : 'badge-count'}`}>
                                                    {item.badge}
                                                </span>
                                            )}

                                            {isActive && <div className="active-indicator"></div>}
                                        </div>

                                        {/* Tooltip for collapsed state */}
                                        {collapsed && (
                                            <div className="nav-tooltip">
                                                <div className="tooltip-content">
                                                    <strong>{item.name}</strong>
                                                    <span>{item.description}</span>
                                                </div>
                                            </div>
                                        )}
                                    </NavLink>
                                </li>
                            );
                        })}
                    </ul>
                </div>

                {/* Quick Actions */}
                <div className="nav-section">
                    <div className="nav-header">
                        {!collapsed && <h3>Quick Actions</h3>}
                    </div>
                    <ul className="nav-list quick-actions">
                        {quickActions.map((item) => (
                            <li key={item.name} className="nav-item">
                                <NavLink
                                    to={item.href}
                                    className="nav-link secondary"
                                >
                                    <div className="nav-link-content">
                                        <div className="nav-icon">
                                            <i className={`bi ${item.icon}`}></i>
                                        </div>
                                        {!collapsed && (
                                            <div className="nav-text">
                                                <span className="nav-title">{item.name}</span>
                                                <small className="nav-description">{item.description}</small>
                                            </div>
                                        )}
                                    </div>

                                    {collapsed && (
                                        <div className="nav-tooltip">
                                            <div className="tooltip-content">
                                                <strong>{item.name}</strong>
                                                <span>{item.description}</span>
                                            </div>
                                        </div>
                                    )}
                                </NavLink>
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Sidebar Footer */}
                <div className="sidebar-footer">
                    <div className="footer-content">
                        {!collapsed ? (
                            <div className="footer-info">
                                <div className="version-info">
                                    <strong>AgentOps Replay</strong>
                                    <span>Version 1.0.0</span>
                                </div>
                                <div className="system-info">
                                    <div className="info-item">
                                        <i className="bi bi-cpu"></i>
                                        <span>System: Active</span>
                                    </div>
                                    <div className="info-item">
                                        <i className="bi bi-hdd"></i>
                                        <span>Storage: 78%</span>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="footer-collapsed">
                                <i className="bi bi-info-circle" title="AgentOps Replay v1.0.0"></i>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    );
});

Sidebar.displayName = 'Sidebar';
export default Sidebar;
