import React from 'react';
import { NavLink } from 'react-router-dom';

const Sidebar = () => {
    return (
        <div className="sidebar">
            <nav className="nav flex-column">
                <NavLink
                    to="/"
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                    <i className="bi bi-speedometer2 me-2"></i>
                    Dashboard
                </NavLink>
                <NavLink
                    to="/sessions"
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                    <i className="bi bi-list-task me-2"></i>
                    Sessions
                </NavLink>
                <NavLink
                    to="/replay"
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                    <i className="bi bi-play-circle me-2"></i>
                    Replay
                </NavLink>
                <NavLink
                    to="/compliance"
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                    <i className="bi bi-shield-check me-2"></i>
                    Compliance
                </NavLink>
                <NavLink
                    to="/live-agent"
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                >
                    <i className="bi bi-robot me-2"></i>
                    Live Agent
                </NavLink>
            </nav>
        </div>
    );
};

export default Sidebar;
