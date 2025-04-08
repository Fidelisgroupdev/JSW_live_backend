import React, { useState, useEffect } from 'react';
import axios from 'axios';

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalBags: 0,
    totalClusters: 0,
    activeCameras: 0,
    pendingAlerts: 0,
    fifoCompliance: 0,
    recentMovements: []
  });

  useEffect(() => {
    // In a real application, we would fetch data from the API
    // For this demo, we'll use mock data
    const fetchData = async () => {
      try {
        setLoading(true);
        // Mock data for demonstration
        setStats({
          totalBags: 1250,
          totalClusters: 15,
          activeCameras: 6,
          pendingAlerts: 3,
          fifoCompliance: 92.5,
          recentMovements: [
            { id: 1, timestamp: '2025-04-01T15:30:00', bag: 'BAG-12345', source: 'Cluster A', destination: 'Cluster B', type: 'internal' },
            { id: 2, timestamp: '2025-04-01T14:45:00', bag: 'BAG-12346', source: 'Warehouse Entry', destination: 'Cluster C', type: 'entry' },
            { id: 3, timestamp: '2025-04-01T14:20:00', bag: 'BAG-12347', source: 'Cluster D', destination: 'Warehouse Exit', type: 'exit' },
            { id: 4, timestamp: '2025-04-01T13:55:00', bag: 'BAG-12348', source: 'Cluster B', destination: 'Cluster E', type: 'internal' },
            { id: 5, timestamp: '2025-04-01T13:30:00', bag: 'BAG-12349', source: 'Warehouse Entry', destination: 'Cluster A', type: 'entry' }
          ]
        });
        setLoading(false);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const formatDateTime = (dateTimeStr) => {
    const date = new Date(dateTimeStr);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getMovementTypeLabel = (type) => {
    switch (type) {
      case 'entry':
        return 'Entry';
      case 'exit':
        return 'Exit';
      case 'internal':
        return 'Internal';
      default:
        return type;
    }
  };

  const getMovementTypeClass = (type) => {
    switch (type) {
      case 'entry':
        return 'success';
      case 'exit':
        return 'warning';
      case 'internal':
        return 'info';
      default:
        return '';
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard data...</div>;
  }

  return (
    <div className="dashboard">
      <h2>Dashboard</h2>
      <p className="page-description">Overview of warehouse operations and key metrics</p>

      <div className="dashboard-grid">
        <div className="card stat-card">
          <span className="stat-label">Total Bags</span>
          <span className="stat-value">{stats.totalBags}</span>
          <span className="material-icons stat-icon">inventory_2</span>
        </div>

        <div className="card stat-card">
          <span className="stat-label">Total Clusters</span>
          <span className="stat-value">{stats.totalClusters}</span>
          <span className="material-icons stat-icon">grid_view</span>
        </div>

        <div className="card stat-card">
          <span className="stat-label">Active Cameras</span>
          <span className="stat-value">{stats.activeCameras}</span>
          <span className="material-icons stat-icon">videocam</span>
        </div>

        <div className="card stat-card">
          <span className="stat-label">Pending Alerts</span>
          <span className="stat-value">{stats.pendingAlerts}</span>
          <span className="material-icons stat-icon">notifications</span>
        </div>
      </div>

      <div className="row">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">FIFO Compliance</h3>
          </div>
          <div className="compliance-meter">
            <div className="meter-value" style={{ width: `${stats.fifoCompliance}%` }}></div>
          </div>
          <div className="meter-label">{stats.fifoCompliance}% Compliant</div>
        </div>
      </div>

      <div className="row">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Recent Movements</h3>
            <button className="btn btn-primary">View All</button>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Bag</th>
                <th>Source</th>
                <th>Destination</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {stats.recentMovements.map(movement => (
                <tr key={movement.id}>
                  <td>{formatDateTime(movement.timestamp)}</td>
                  <td>{movement.bag}</td>
                  <td>{movement.source}</td>
                  <td>{movement.destination}</td>
                  <td>
                    <span className={`badge ${getMovementTypeClass(movement.type)}`}>
                      {getMovementTypeLabel(movement.type)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
