import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';

// Components
import Dashboard from './components/Dashboard';
import ClusterManagement from './components/ClusterManagement';
import CameraMonitoring from './components/CameraMonitoring';
import CameraMonitor from './components/CameraMonitor';
import InventoryManagement from './components/InventoryManagement';
import Analytics from './components/Analytics';
import Alerts from './components/Alerts';
import RTSPTester from './components/RTSPTester';

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const toggleSidebar = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <Router>
      <div className="app">
        <header className="app-header">
          <div className="header-left">
            <button className="menu-toggle" onClick={toggleSidebar}>
              <span className="material-icons">menu</span>
            </button>
            <h1>CementTrack</h1>
          </div>
          <div className="header-right">
            <span className="user-info">Admin User</span>
          </div>
        </header>
        <div className="app-container">
          <aside className={`app-sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
            <nav className="sidebar-nav">
              <ul>
                <li>
                  <Link to="/">
                    <span className="material-icons">dashboard</span>
                    <span className="nav-text">Dashboard</span>
                  </Link>
                </li>
                <li>
                  <Link to="/clusters">
                    <span className="material-icons">grid_view</span>
                    <span className="nav-text">Cluster Management</span>
                  </Link>
                </li>
                <li>
                  <Link to="/cameras">
                    <span className="material-icons">videocam</span>
                    <span className="nav-text">Camera Monitoring</span>
                  </Link>
                </li>
                <li>
                  <Link to="/advanced-camera-monitor">
                    <span className="material-icons">video_camera_front</span>
                    <span className="nav-text">Advanced Camera Monitor</span>
                  </Link>
                </li>
                <li>
                  <Link to="/rtsp-tester">
                    <span className="material-icons">live_tv</span>
                    <span className="nav-text">RTSP Tester</span>
                  </Link>
                </li>
                <li>
                  <Link to="/inventory">
                    <span className="material-icons">inventory_2</span>
                    <span className="nav-text">Inventory Management</span>
                  </Link>
                </li>
                <li>
                  <Link to="/analytics">
                    <span className="material-icons">analytics</span>
                    <span className="nav-text">Analytics</span>
                  </Link>
                </li>
                <li>
                  <Link to="/alerts">
                    <span className="material-icons">notifications</span>
                    <span className="nav-text">Alerts</span>
                  </Link>
                </li>
              </ul>
            </nav>
          </aside>
          <main className="app-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/clusters" element={<ClusterManagement />} />
              <Route path="/cameras" element={<CameraMonitoring />} />
              <Route path="/advanced-camera-monitor" element={<CameraMonitor />} />
              <Route path="/rtsp-tester" element={<RTSPTester />} />
              <Route path="/inventory" element={<InventoryManagement />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/alerts" element={<Alerts />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;
