/* eslint-disable no-unused-vars */
import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import Confetti from 'react-confetti';
import { apiService } from '../services/api';

gsap.registerPlugin(ScrollTrigger);

const Replay = () => {
    const { sessionId: urlSessionId } = useParams();
    const [sessions, setSessions] = useState([]);
    const [selectedSession, setSelectedSession] = useState(urlSessionId || '');
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(false);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentEventIndex, setCurrentEventIndex] = useState(0);
    const [sessionDetails, setSessionDetails] = useState(null);
    const [playbackSpeed, setPlaybackSpeed] = useState(1);
    const [showCelebration, setShowCelebration] = useState(false);

    const replayContainerRef = useRef();
    const progressBarRef = useRef();
    const eventsTimelineRef = useRef();
    const playbackInterval = useRef();

    // Your existing useEffect hooks and functions here...

    useEffect(() => {
        fetchSessions();
    }, []);

    useEffect(() => {
        if (selectedSession) {
            fetchSessionEvents(selectedSession);
            fetchSessionDetails(selectedSession);
        }
    }, [selectedSession]);

    const fetchSessions = async () => {
        try {
            const response = await apiService.getSessions();
            setSessions(response.data);
        } catch (error) {
            console.error('Error fetching sessions:', error);
            toast.error('Failed to load sessions');
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
            const sortedEvents = response.data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            setEvents(sortedEvents);
            setCurrentEventIndex(0);
            setLoading(false);

            if (sortedEvents.length > 0) {
                toast.success(`📊 ${sortedEvents.length} events loaded for replay`);
            }
        } catch (error) {
            console.error('Error fetching events:', error);
            toast.error('Failed to load session events');
            setLoading(false);
        }
    };

    // Enhanced Event Item Component with Action Buttons
    const EventItem = ({ event, index, isActive, isCompleted }) => {
        const [isHovered, setIsHovered] = useState(false);

        const handleViewDetails = () => {
            toast.success(`Event Details:\nType: ${event.event_type}\nTool: ${event.tool_name || 'N/A'}\nFlags: ${event.flags?.join(', ') || 'None'}`);
        };

        const handleJumpToEvent = () => {
            jumpToEvent(index);
        };

        const handleCopyEvent = () => {
            const eventData = {
                type: event.event_type,
                tool: event.tool_name,
                timestamp: event.timestamp,
                flags: event.flags
            };
            navigator.clipboard.writeText(JSON.stringify(eventData, null, 2));
            toast.success('Event data copied to clipboard!');
        };

        return (
            <motion.div
                className={`enhanced-event-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5, delay: index * 0.05 }}
                whileHover={{
                    scale: 1.02,
                    boxShadow: "0 8px 25px rgba(52, 152, 219, 0.15)"
                }}
                onHoverStart={() => setIsHovered(true)}
                onHoverEnd={() => setIsHovered(false)}
            >
                {/* Event Status Indicator */}
                <div className="event-status-indicator">
                    <AnimatePresence mode="wait">
                        {isCompleted && (
                            <motion.i
                                className="bi bi-check-circle-fill text-success"
                                initial={{ scale: 0, rotate: -180 }}
                                animate={{ scale: 1, rotate: 0 }}
                                exit={{ scale: 0, rotate: 180 }}
                                transition={{ type: "spring", stiffness: 300 }}
                                key="completed"
                            />
                        )}
                        {isActive && (
                            <motion.i
                                className="bi bi-play-circle-fill text-primary"
                                initial={{ scale: 0 }}
                                animate={{
                                    scale: 1,
                                    rotate: [0, 360]
                                }}
                                transition={{
                                    type: "spring",
                                    stiffness: 400,
                                    rotate: { duration: 2, repeat: Infinity, ease: "linear" }
                                }}
                                key="active"
                            />
                        )}
                        {!isCompleted && !isActive && (
                            <motion.i
                                className="bi bi-circle text-muted"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                whileHover={{ scale: 1.2, color: "#3498db" }}
                                key="inactive"
                            />
                        )}
                    </AnimatePresence>
                </div>

                {/* Event Content */}
                <div className="event-content">
                    <div className="event-header">
                        <div className="event-main-info">
                            <h6 className="event-title">
                                {event.event_type}
                                <span className="event-sequence-badge">#{index + 1}</span>
                            </h6>

                            {event.tool_name && (
                                <div className="event-tool-info">
                                    <i className="bi bi-tools me-1"></i>
                                    <strong>Tool:</strong> {event.tool_name}
                                </div>
                            )}
                        </div>

                        {/* Action Buttons */}
                        <motion.div
                            className="event-actions"
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{
                                opacity: isHovered ? 1 : 0.7,
                                scale: isHovered ? 1 : 0.9
                            }}
                            transition={{ duration: 0.2 }}
                        >
                            <button
                                className="btn btn-sm btn-outline-primary me-1"
                                onClick={handleViewDetails}
                                title="View Event Details"
                            >
                                <i className="bi bi-info-circle"></i>
                            </button>
                            <button
                                className="btn btn-sm btn-outline-success me-1"
                                onClick={handleJumpToEvent}
                                title="Jump to Event"
                            >
                                <i className="bi bi-skip-forward"></i>
                            </button>
                            <button
                                className="btn btn-sm btn-outline-secondary"
                                onClick={handleCopyEvent}
                                title="Copy Event Data"
                            >
                                <i className="bi bi-clipboard"></i>
                            </button>
                        </motion.div>
                    </div>

                    {/* Event Flags */}
                    {event.flags && event.flags.length > 0 && (
                        <div className="event-flags">
                            {event.flags.map((flag, flagIndex) => (
                                <span
                                    key={flag}
                                    className="flag-badge me-1 mb-1"
                                    style={{
                                        animationDelay: `${flagIndex * 0.1}s`
                                    }}
                                >
                                    <i className="bi bi-flag-fill me-1"></i>
                                    {flag}
                                </span>
                            ))}
                        </div>
                    )}

                    {/* Event Timestamp */}
                    <div className="event-timestamp">
                        <i className="bi bi-clock me-1"></i>
                        {new Date(event.timestamp).toLocaleString()}
                    </div>
                </div>

                {/* Active Event Glow Effect */}
                {isActive && (
                    <motion.div
                        className="active-glow-effect"
                        initial={{ opacity: 0 }}
                        animate={{
                            opacity: [0, 0.3, 0],
                        }}
                        transition={{
                            duration: 1.5,
                            repeat: Infinity,
                            ease: "easeInOut"
                        }}
                    />
                )}
            </motion.div>
        );
    };

    // Your existing control functions
    const startReplay = () => {
        setIsPlaying(true);
        setCurrentEventIndex(0);
        toast.success('🎬 Replay started!');

        if (events.length > 10) {
            setShowCelebration(true);
            setTimeout(() => setShowCelebration(false), 2000);
        }

        if (playbackInterval.current) {
            clearInterval(playbackInterval.current);
        }

        let index = 0;
        playbackInterval.current = setInterval(() => {
            if (index >= events.length - 1) {
                setIsPlaying(false);
                clearInterval(playbackInterval.current);
                toast.success('🎉 Replay completed successfully!');
                return;
            }

            index++;
            setCurrentEventIndex(index);
        }, (1000 / playbackSpeed));
    };

    const stopReplay = () => {
        setIsPlaying(false);
        if (playbackInterval.current) {
            clearInterval(playbackInterval.current);
        }
        toast.info('⏸️ Replay paused');
    };

    const resetReplay = () => {
        setIsPlaying(false);
        setCurrentEventIndex(0);
        if (playbackInterval.current) {
            clearInterval(playbackInterval.current);
        }
        toast.info('🔄 Replay reset to beginning');
    };

    const jumpToEvent = (index) => {
        setCurrentEventIndex(index);
        if (isPlaying) {
            stopReplay();
        }
        toast.info(`⏭️ Jumped to event #${index + 1}`);

        // Scroll to event in timeline
        const eventElement = document.querySelector(`.enhanced-event-item:nth-child(${index + 1})`);
        if (eventElement) {
            eventElement.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }
    };

    if (loading) {
        return (
            <div className="loading-container">
                <div className="loading-skeleton">
                    <div className="d-flex justify-content-center align-items-center" style={{ height: '400px' }}>
                        <div className="spinner-border text-primary" role="status">
                            <span className="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="replay-container" ref={replayContainerRef}>
            {showCelebration && <Confetti numberOfPieces={150} recycle={false} />}

            {/* Header Section */}
            <section className="replay-header-section">
                <motion.div
                    className="d-flex justify-content-between align-items-center mb-4"
                    initial={{ opacity: 0, y: -30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <div>
                        <h1 className="replay-title">
                            <i className="bi bi-play-circle me-3 text-primary"></i>
                            <span className="gradient-text">Session Replay</span>
                        </h1>
                        {sessionDetails && (
                            <motion.p
                                className="session-subtitle"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.3 }}
                            >
                                <strong>Agent:</strong> {sessionDetails.agent_name || 'Unknown Agent'}
                                <span className={`badge status-${sessionDetails.status} ms-2`}>
                                    {sessionDetails.status}
                                </span>
                            </motion.p>
                        )}
                    </div>

                    <div className="replay-controls">
                        {selectedSession && events.length > 0 && (
                            <div className="speed-control me-3">
                                <small className="text-muted me-2">Speed:</small>
                                <select
                                    className="form-select form-select-sm"
                                    value={playbackSpeed}
                                    onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
                                    disabled={isPlaying}
                                >
                                    <option value={0.5}>0.5x</option>
                                    <option value={1}>1x</option>
                                    <option value={1.5}>1.5x</option>
                                    <option value={2}>2x</option>
                                    <option value={3}>3x</option>
                                </select>
                            </div>
                        )}

                        {selectedSession && (
                            <div className="control-buttons">
                                <button
                                    className="btn btn-success me-2"
                                    onClick={startReplay}
                                    disabled={isPlaying || events.length === 0}
                                >
                                    <i className="bi bi-play-fill me-2"></i>
                                    Start
                                </button>

                                <button
                                    className="btn btn-warning me-2"
                                    onClick={resetReplay}
                                    disabled={isPlaying}
                                >
                                    <i className="bi bi-arrow-counterclockwise me-2"></i>
                                    Reset
                                </button>

                                <button
                                    className="btn btn-danger"
                                    onClick={stopReplay}
                                    disabled={!isPlaying}
                                >
                                    <i className="bi bi-stop-fill me-2"></i>
                                    Stop
                                </button>
                            </div>
                        )}
                    </div>
                </motion.div>
            </section>

            {/* Session Selection Section */}
            <section className="session-selection-section">
                <motion.div
                    className="card border-0 shadow-lg mb-4"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0.1 }}
                >
                    <div className="card-header bg-gradient-primary text-black">
                        <h5 className="mb-0">
                            <i className="bi bi-collection-play me-2"></i>
                            Session Selection
                        </h5>
                    </div>
                    <div className="card-body">
                        <div className="row align-items-end">
                            <div className="col-md-8">
                                <label className="form-label fw-semibold">
                                    Select Session to Replay
                                </label>
                                <select
                                    className="form-control session-selector"
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
                                    <motion.div
                                        className="session-stats-card"
                                        initial={{ opacity: 0, scale: 0.8 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        transition={{ duration: 0.4 }}
                                    >
                                        <div className="stat-item">
                                            <i className="bi bi-lightning-fill text-warning me-2"></i>
                                            <strong>{events.length}</strong> Events
                                        </div>
                                        <div className="stat-item">
                                            <i className="bi bi-clock text-info me-2"></i>
                                            <strong>{Math.ceil(events.length / playbackSpeed)}</strong>s Duration
                                        </div>
                                    </motion.div>
                                )}
                            </div>
                        </div>
                    </div>
                </motion.div>
            </section>

            {/* Progress Section */}
            {selectedSession && events.length > 0 && (
                <section className="progress-section">
                    <motion.div
                        className="card border-0 shadow-lg mb-4"
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.2 }}
                    >
                        <div className="card-body">
                            <div className="d-flex justify-content-between align-items-center mb-3">
                                <div className="progress-info">
                                    <i className="bi bi-clock-history me-2 text-primary"></i>
                                    <span className="fw-bold">Replay Progress</span>
                                </div>
                                <motion.span
                                    className="badge bg-primary fs-6 progress-counter"
                                    animate={{ scale: isPlaying ? [1, 1.1, 1] : 1 }}
                                    transition={{ duration: 1, repeat: isPlaying ? Infinity : 0 }}
                                >
                                    {currentEventIndex + 1} / {events.length}
                                </motion.span>
                            </div>

                            <div className="enhanced-progress-bar">
                                <div
                                    ref={progressBarRef}
                                    className="progress-fill"
                                    style={{
                                        width: `${((currentEventIndex + 1) / events.length) * 100}%`,
                                        transition: 'width 0.3s ease'
                                    }}
                                ></div>
                            </div>

                            <div className="d-flex justify-content-between mt-2">
                                <small className="text-muted timestamp-start">
                                    {events.length > 0 ? new Date(events[0].timestamp).toLocaleString() : ''}
                                </small>
                                <small className="text-muted timestamp-end">
                                    {events.length > 0 ? new Date(events[events.length - 1].timestamp).toLocaleString() : ''}
                                </small>
                            </div>
                        </div>
                    </motion.div>
                </section>
            )}

            {/* Enhanced Events Timeline Section */}
            {selectedSession && events.length > 0 ? (
                <section className="events-timeline-section">
                    <motion.div
                        className="timeline-container"
                        ref={eventsTimelineRef}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.8, delay: 0.3 }}
                    >
                        <div className="timeline-header">
                            <div className="d-flex align-items-center justify-content-between mb-4">
                                <div className="timeline-title-section">
                                    <h5 className="timeline-title">
                                        <i className="bi bi-diagram-3 me-2 text-primary"></i>
                                        Session Events Timeline
                                    </h5>
                                    <p className="timeline-subtitle text-muted">
                                        Interactive timeline showing all {events.length} events in chronological order
                                    </p>
                                </div>

                                <div className="timeline-actions">
                                    <button
                                        className="btn btn-sm btn-outline-primary me-2"
                                        onClick={() => {
                                            const container = document.querySelector('.scrollable-events-container');
                                            if (container) container.scrollTop = 0;
                                        }}
                                    >
                                        <i className="bi bi-arrow-up"></i>
                                        Top
                                    </button>
                                    <button
                                        className="btn btn-sm btn-outline-info"
                                        onClick={() => {
                                            const container = document.querySelector('.scrollable-events-container');
                                            if (container) container.scrollTop = container.scrollHeight;
                                        }}
                                    >
                                        <i className="bi bi-arrow-down"></i>
                                        Bottom
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Scrollable Events Container */}
                        <div className="scrollable-events-container">
                            <div className="events-list">
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
                        </div>

                        {/* Scroll Indicators */}
                        <div className="scroll-indicators">
                            <small className="text-muted">
                                <i className="bi bi-mouse me-1"></i>
                                Scroll to view all events • Click buttons to interact
                            </small>
                        </div>
                    </motion.div>
                </section>
            ) : selectedSession ? (
                <section className="empty-events-section">
                    <motion.div
                        className="text-center py-5"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.6 }}
                    >
                        <motion.i
                            className="bi bi-inbox display-1 text-muted mb-4"
                            animate={{ y: [0, -10, 0] }}
                            transition={{ duration: 2, repeat: Infinity }}
                        ></motion.i>
                        <h4 className="text-muted">No Events Found</h4>
                        <p className="text-muted">This session doesn't have any events to replay</p>
                        <button
                            className="btn btn-primary mt-3"
                            onClick={() => window.location.href = '/sessions'}
                        >
                            <i className="bi bi-plus-circle me-2"></i>
                            Generate Events
                        </button>
                    </motion.div>
                </section>
            ) : (
                <section className="session-selection-prompt">
                    <motion.div
                        className="text-center py-5"
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: 0.6 }}
                    >
                        <motion.i
                            className="bi bi-play-circle display-1 text-primary mb-4"
                            animate={{
                                rotate: [0, 360],
                                scale: [1, 1.1, 1]
                            }}
                            transition={{
                                rotate: { duration: 10, repeat: Infinity, ease: "linear" },
                                scale: { duration: 2, repeat: Infinity }
                            }}
                        ></motion.i>
                        <h4 className="text-muted">Select a Session</h4>
                        <p className="text-muted">Choose a session from the dropdown above to start replay</p>
                    </motion.div>
                </section>
            )}
        </div>
    );
};

export default Replay;
