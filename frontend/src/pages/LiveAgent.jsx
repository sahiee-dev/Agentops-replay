import React, { useState } from 'react';
import { apiService } from '../services/api';

const LiveAgent = () => {
    const [messages, setMessages] = useState([]);
    const [currentMessage, setCurrentMessage] = useState('');
    const [sessionId, setSessionId] = useState(null);
    const [isAgentActive, setIsAgentActive] = useState(false);
    const [isTyping, setIsTyping] = useState(false);

    const startAgentSession = async () => {
        try {
            const response = await apiService.startAgentSession();
            setSessionId(response.data.session_id);
            setIsAgentActive(true);

            setMessages([{
                type: 'system',
                content: `Customer Support Agent started (Session #${response.data.session_id})`,
                timestamp: new Date().toISOString()
            }, {
                type: 'agent',
                content: 'Hello! I\'m your customer support agent. How can I help you today?',
                timestamp: new Date().toISOString()
            }]);

        } catch (error) {
            console.error('Error starting agent session:', error);
        }
    };

    const sendMessage = async () => {
        if (!currentMessage.trim() || !sessionId) return;

        const userMessage = {
            type: 'user',
            content: currentMessage,
            timestamp: new Date().toISOString()
        };

        setMessages(prev => [...prev, userMessage]);
        setCurrentMessage('');
        setIsTyping(true);

        try {
            const response = await apiService.chatWithAgent({
                message: currentMessage,
                session_id: sessionId
            });

            const agentMessage = {
                type: 'agent',
                content: response.data.response,
                timestamp: new Date().toISOString()
            };

            setMessages(prev => [...prev, agentMessage]);
            setIsTyping(false);

        } catch (error) {
            console.error('Error sending message:', error);
            setIsTyping(false);
        }
    };

    const endSession = async () => {
        if (!sessionId) return;

        try {
            await apiService.endAgentSession(sessionId);
            setIsAgentActive(false);
            setSessionId(null);

            setMessages(prev => [...prev, {
                type: 'system',
                content: 'Customer support session ended',
                timestamp: new Date().toISOString()
            }]);

        } catch (error) {
            console.error('Error ending session:', error);
        }
    };

    const sampleQuestions = [
        "I need help with my order status",
        "I want to request a refund",
        "My account login isn't working",
        "How do I update my billing information?"
    ];

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h1>Live Customer Support Agent</h1>
                    {sessionId && (
                        <p className="text-muted mb-0">
                            Active Session: #{sessionId}
                            <span className="badge bg-success ms-2">Live Agent</span>
                        </p>
                    )}
                </div>
                <div className="d-flex gap-2">
                    {!isAgentActive ? (
                        <button className="btn btn-success" onClick={startAgentSession}>
                            <i className="bi bi-play-circle me-2"></i>
                            Start Agent Session
                        </button>
                    ) : (
                        <>
                            <a
                                href={`/replay/${sessionId}`}
                                className="btn btn-outline-primary"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                <i className="bi bi-eye me-2"></i>
                                View Live Replay
                            </a>
                            <button className="btn btn-danger" onClick={endSession}>
                                <i className="bi bi-stop-circle me-2"></i>
                                End Session
                            </button>
                        </>
                    )}
                </div>
            </div>

            {!isAgentActive ? (
                <div className="card">
                    <div className="card-body text-center py-5">
                        <i className="bi bi-robot fs-1 text-muted mb-3"></i>
                        <h4>Customer Support Agent Demo</h4>
                        <p className="text-muted mb-4">
                            Start a live customer support session to see real-time event logging and replay in action.
                        </p>
                        <button className="btn btn-primary btn-lg" onClick={startAgentSession}>
                            <i className="bi bi-chat-dots me-2"></i>
                            Start Live Demo
                        </button>
                    </div>
                </div>
            ) : (
                <div className="row">
                    {/* Chat Interface */}
                    <div className="col-md-8">
                        <div className="card">
                            <div className="card-header">
                                <h6 className="mb-0">
                                    <i className="bi bi-chat-square-dots me-2"></i>
                                    Chat with Customer Support Agent
                                </h6>
                            </div>
                            <div className="card-body">
                                {/* Messages */}
                                <div className="chat-messages mb-3" style={{ height: '400px', overflowY: 'auto' }}>
                                    {messages.map((msg, index) => (
                                        <div key={index} className={`message ${msg.type}`} style={{ marginBottom: '1rem' }}>
                                            {msg.type === 'user' && (
                                                <div className="d-flex justify-content-end">
                                                    <div className="bg-primary text-white rounded px-3 py-2 max-width-70">
                                                        {msg.content}
                                                    </div>
                                                </div>
                                            )}
                                            {msg.type === 'agent' && (
                                                <div className="d-flex justify-content-start">
                                                    <div className="bg-light rounded px-3 py-2 max-width-70">
                                                        <strong>🤖 Support Agent:</strong><br />
                                                        {msg.content}
                                                    </div>
                                                </div>
                                            )}
                                            {msg.type === 'system' && (
                                                <div className="text-center">
                                                    <small className="text-muted fst-italic">{msg.content}</small>
                                                </div>
                                            )}
                                        </div>
                                    ))}

                                    {isTyping && (
                                        <div className="d-flex justify-content-start">
                                            <div className="bg-light rounded px-3 py-2">
                                                <span className="typing-indicator">
                                                    🤖 Agent is typing
                                                    <span className="dots">
                                                        <span>.</span><span>.</span><span>.</span>
                                                    </span>
                                                </span>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Input */}
                                <div className="input-group">
                                    <input
                                        type="text"
                                        className="form-control"
                                        placeholder="Type your message..."
                                        value={currentMessage}
                                        onChange={(e) => setCurrentMessage(e.target.value)}
                                        onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                                    />
                                    <button
                                        className="btn btn-primary"
                                        onClick={sendMessage}
                                        disabled={!currentMessage.trim()}
                                    >
                                        <i className="bi bi-send"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Quick Actions */}
                    <div className="col-md-4">
                        <div className="card">
                            <div className="card-header">
                                <h6 className="mb-0">Quick Test Questions</h6>
                            </div>
                            <div className="card-body">
                                {sampleQuestions.map((question, index) => (
                                    <button
                                        key={index}
                                        className="btn btn-outline-secondary btn-sm w-100 mb-2 text-start"
                                        onClick={() => setCurrentMessage(question)}
                                    >
                                        {question}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="card mt-3">
                            <div className="card-header">
                                <h6 className="mb-0">Live Monitoring</h6>
                            </div>
                            <div className="card-body">
                                <div className="d-flex flex-column gap-2">
                                    <a
                                        href={`/replay/${sessionId}`}
                                        className="btn btn-sm btn-outline-primary"
                                        target="_blank"
                                    >
                                        <i className="bi bi-play me-1"></i>
                                        Watch Live Replay
                                    </a>
                                    <a
                                        href={`/compliance/${sessionId}`}
                                        className="btn btn-sm btn-outline-info"
                                        target="_blank"
                                    >
                                        <i className="bi bi-shield-check me-1"></i>
                                        Live Compliance
                                    </a>
                                    <a
                                        href="/dashboard"
                                        className="btn btn-sm btn-outline-success"
                                        target="_blank"
                                    >
                                        <i className="bi bi-speedometer2 me-1"></i>
                                        Dashboard
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default LiveAgent;
