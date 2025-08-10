import React, { useState, useEffect } from 'react';
import { apiService } from '../../services/api';

const QuickEventGenerator = ({ sessionId, onEventsGenerated }) => {
    const [scenarios, setScenarios] = useState([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [lastGenerated, setLastGenerated] = useState(null);

    useEffect(() => {
        fetchScenarios();
    }, []);

    const fetchScenarios = async () => {
        try {
            const response = await apiService.getEventScenarios();
            setScenarios(response.data.scenarios);
        } catch (error) {
            console.error('Error fetching scenarios:', error);
        }
    };

    const generateEvents = async (scenarioType) => {
        setIsGenerating(true);

        try {
            const response = await apiService.generateEvents({
                session_id: sessionId,
                scenario_type: scenarioType
            });

            setLastGenerated(response.data);

            // Show success message
            alert(`✅ ${response.data.message}`);

            // Notify parent component to refresh
            if (onEventsGenerated) {
                onEventsGenerated();
            }

        } catch (error) {
            console.error('Error generating events:', error);
            alert('❌ Error generating events: ' + (error.response?.data?.detail || error.message));
        } finally {
            setIsGenerating(false);
        }
    };

    return (
        <div className="card">
            <div className="card-header">
                <h6 className="mb-0">
                    <i className="bi bi-magic me-2"></i>
                    Event Generator - Session #{sessionId}
                </h6>
            </div>
            <div className="card-body">
                <p className="text-muted mb-3">
                    Generate realistic agent workflows instantly by selecting a scenario:
                </p>

                {/* Success message */}
                {lastGenerated && (
                    <div className="alert alert-success alert-dismissible fade show" role="alert">
                        <i className="bi bi-check-circle me-2"></i>
                        Generated <strong>{lastGenerated.events_created} events</strong> for {lastGenerated.scenario_type}
                        <button
                            type="button"
                            className="btn-close"
                            onClick={() => setLastGenerated(null)}
                        ></button>
                    </div>
                )}

                {/* Scenario buttons */}
                <div className="row">
                    {scenarios.map((scenario) => (
                        <div key={scenario.type} className="col-md-6 mb-3">
                            <div className="card h-100">
                                <div className="card-body">
                                    <h6 className="card-title">
                                        {getScenarioIcon(scenario.type)}
                                        {scenario.name}
                                    </h6>
                                    <p className="card-text text-muted small mb-2">
                                        {scenario.description}
                                    </p>
                                    <p className="text-muted small mb-3">
                                        <i className="bi bi-lightning me-1"></i>
                                        {scenario.events_count} events
                                    </p>
                                    <button
                                        className={`btn btn-sm w-100 ${getScenarioButtonClass(scenario.type)}`}
                                        onClick={() => generateEvents(scenario.type)}
                                        disabled={isGenerating}
                                    >
                                        {isGenerating ? (
                                            <>
                                                <span className="spinner-border spinner-border-sm me-2"></span>
                                                Generating...
                                            </>
                                        ) : (
                                            <>
                                                <i className="bi bi-play me-1"></i>
                                                Generate
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {isGenerating && (
                    <div className="text-center mt-3">
                        <div className="spinner-border text-primary me-2"></div>
                        <span>Creating realistic agent events...</span>
                    </div>
                )}
            </div>
        </div>
    );
};

// Helper functions
const getScenarioIcon = (type) => {
    const icons = {
        customer_support: <i className="bi bi-headset me-2 text-primary"></i>,
        data_analysis: <i className="bi bi-bar-chart me-2 text-info"></i>,
        voice_agent: <i className="bi bi-telephone me-2 text-success"></i>,
        complex_workflow: <i className="bi bi-exclamation-triangle me-2 text-warning"></i>
    };
    return icons[type] || <i className="bi bi-gear me-2"></i>;
};

const getScenarioButtonClass = (type) => {
    const classes = {
        customer_support: 'btn-primary',
        data_analysis: 'btn-info',
        voice_agent: 'btn-success',
        complex_workflow: 'btn-warning'
    };
    return classes[type] || 'btn-secondary';
};

export default QuickEventGenerator;
