import React, { useRef, useLayoutEffect, useState } from 'react';
import { gsap } from 'gsap';
import Header from './Header';
import Sidebar from './Sidebar';

const Layout = ({ children }) => {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const layoutRef = useRef();
    const headerRef = useRef();
    const sidebarRef = useRef();
    const mainRef = useRef();

    useLayoutEffect(() => {
        // Simple, smooth fade-in animation
        if (headerRef.current && sidebarRef.current && mainRef.current) {
            gsap.set([headerRef.current, sidebarRef.current, mainRef.current], {
                opacity: 0
            });

            const tl = gsap.timeline();
            tl.to(headerRef.current, { opacity: 1, duration: 0.4, ease: "power2.out" })
                .to(sidebarRef.current, { opacity: 1, duration: 0.4, ease: "power2.out" }, 0.1)
                .to(mainRef.current, { opacity: 1, duration: 0.4, ease: "power2.out" }, 0.2);
        }
    }, []);

    const handleToggleSidebar = () => {
        setSidebarCollapsed(!sidebarCollapsed);
    };

    return (
        <div className="layout-container" ref={layoutRef}>
            <Header
                ref={headerRef}
                sidebarCollapsed={sidebarCollapsed}
                onToggleSidebar={handleToggleSidebar}
            />

            <div className="layout-body">
                <Sidebar
                    ref={sidebarRef}
                    collapsed={sidebarCollapsed}
                    onToggle={handleToggleSidebar}
                />

                <main
                    ref={mainRef}
                    className={`main-content ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}
                >
                    <div className="content-wrapper">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    );
};

export default Layout;
