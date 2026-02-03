import React from 'react';
import Header from './Header';
import Sidebar from './Sidebar';

const Layout = ({ children }) => {
    return (
        <div className="app">
            <Header />
            <div className="d-flex">
                <Sidebar />
                <main className="main-content flex-grow-1">
                    {children}
                </main>
            </div>
        </div>
    );
};

export default Layout;
