import React from 'react';

const Header = () => {
    return (
        <nav className="navbar navbar-expand-lg navbar-light app-header">
            <div className="container-fluid">
                <a className="navbar-brand" href="/">
                    <i className="bi bi-play-circle me-2"></i>
                    AgentOps Replay
                </a>
                <div className="navbar-nav ms-auto">
                    <span className="nav-link">
                        <i className="bi bi-circle-fill text-success me-1"></i>
                        Backend Connected
                    </span>
                </div>
            </div>
        </nav>
    );
};

export default Header;
