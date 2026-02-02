import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Sessions from './pages/Sessions';
import Replay from './pages/Replay';
import Compliance from './pages/Compliance';
import LiveAgent from './pages/LiveAgent';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/replay" element={<Replay />} />
          <Route path="/replay/:sessionId" element={<Replay />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/compliance/:sessionId" element={<Compliance />} />
          <Route path="/live-agent" element={<LiveAgent />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
