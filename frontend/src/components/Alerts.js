import React, { useState, useEffect } from 'react';
import axios from 'axios';

const Alerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    severity: '',
    type: '',
    status: 'active'
  });

  useEffect(() => {
    // In a real application, we would fetch data from the API
    // For this demo, we'll use mock data
    const fetchAlerts = async () => {
      try {
        setLoading(true);
        // Mock alerts data
        setAlerts([
          { id: 1, type: 'fifo_violation', message: 'FIFO violation detected in Cluster A', timestamp: '2025-04-07 09:15:22', severity: 'high', status: 'active', cluster: 'Cluster A' },
          { id: 2, type: 'capacity_warning', message: 'Cluster A approaching maximum capacity (91.7%)', timestamp: '2025-04-07 10:30:45', severity: 'medium', status: 'active', cluster: 'Cluster A' },
          { id: 3, type: 'shelf_life', message: '25 bags in Cluster B approaching shelf life limit', timestamp: '2025-04-06 14:22:10', severity: 'high', status: 'active', cluster: 'Cluster B' },
          { id: 4, type: 'camera_issue', message: 'Camera 2 connection unstable', timestamp: '2025-04-06 08:45:33', severity: 'low', status: 'active', cluster: null },
          { id: 5, type: 'movement_anomaly', message: 'Unusual movement pattern detected in Cluster C', timestamp: '2025-04-05 16:10:05', severity: 'medium', status: 'active', cluster: 'Cluster C' },
          { id: 6, type: 'fifo_violation', message: 'FIFO violation detected in Cluster D', timestamp: '2025-04-05 11:30:18', severity: 'high', status: 'resolved', cluster: 'Cluster D' },
          { id: 7, type: 'shelf_life', message: '10 bags in Cluster E approaching shelf life limit', timestamp: '2025-04-04 15:45:22', severity: 'medium', status: 'resolved', cluster: 'Cluster E' },
          { id: 8, type: 'capacity_warning', message: 'Cluster B approaching maximum capacity (85.2%)', timestamp: '2025-04-04 09:20:15', severity: 'medium', status: 'resolved', cluster: 'Cluster B' },
          { id: 9, type: 'camera_issue', message: 'Camera 4 connection lost', timestamp: '2025-04-03 14:10:33', severity: 'high', status: 'resolved', cluster: null },
          { id: 10, type: 'movement_anomaly', message: 'Unusual movement pattern detected in Cluster A', timestamp: '2025-04-03 10:05:45', severity: 'medium', status: 'resolved', cluster: 'Cluster A' }
        ]);
        setLoading(false);
      } catch (error) {
        console.error('Error fetching alerts:', error);
        setLoading(false);
      }
    };

    fetchAlerts();
  }, []);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilter({
      ...filter,
      [name]: value
    });
  };

  const getSeverityClass = (severity) => {
    switch (severity) {
      case 'high':
        return 'severity-high';
      case 'medium':
        return 'severity-medium';
      case 'low':
        return 'severity-low';
      default:
        return '';
    }
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'high':
        return 'error';
      case 'medium':
        return 'warning';
      case 'low':
        return 'info';
      default:
        return 'help';
    }
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case 'fifo_violation':
        return 'swap_vert';
      case 'capacity_warning':
        return 'inventory_2';
      case 'shelf_life':
        return 'schedule';
      case 'camera_issue':
        return 'videocam_off';
      case 'movement_anomaly':
        return 'trending_up';
      default:
        return 'notifications';
    }
  };

  const getTypeLabel = (type) => {
    switch (type) {
      case 'fifo_violation':
        return 'FIFO Violation';
      case 'capacity_warning':
        return 'Capacity Warning';
      case 'shelf_life':
        return 'Shelf Life Alert';
      case 'camera_issue':
        return 'Camera Issue';
      case 'movement_anomaly':
        return 'Movement Anomaly';
      default:
        return type;
    }
  };

  const handleResolve = (id) => {
    setAlerts(alerts.map(alert => 
      alert.id === id ? { ...alert, status: 'resolved' } : alert
    ));
  };

  const applyFilters = () => {
    return alerts.filter(alert => {
      // Filter by severity
      if (filter.severity && alert.severity !== filter.severity) {
        return false;
      }
      
      // Filter by type
      if (filter.type && alert.type !== filter.type) {
        return false;
      }
      
      // Filter by status
      if (filter.status && alert.status !== filter.status) {
        return false;
      }
      
      return true;
    });
  };

  if (loading) {
    return <div className="loading">Loading alerts...</div>;
  }

  const filteredAlerts = applyFilters();

  return (
    <div className="alerts">
      <h2>Alerts & Notifications</h2>
      <p className="page-description">Monitor and manage system alerts and notifications</p>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Alert Management</h3>
          <div className="filter-controls">
            <div className="filter-group">
              <label>Severity</label>
              <select name="severity" value={filter.severity} onChange={handleFilterChange}>
                <option value="">All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div className="filter-group">
              <label>Type</label>
              <select name="type" value={filter.type} onChange={handleFilterChange}>
                <option value="">All</option>
                <option value="fifo_violation">FIFO Violation</option>
                <option value="capacity_warning">Capacity Warning</option>
                <option value="shelf_life">Shelf Life Alert</option>
                <option value="camera_issue">Camera Issue</option>
                <option value="movement_anomaly">Movement Anomaly</option>
              </select>
            </div>
            <div className="filter-group">
              <label>Status</label>
              <select name="status" value={filter.status} onChange={handleFilterChange}>
                <option value="">All</option>
                <option value="active">Active</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
          </div>
        </div>

        <div className="alerts-list">
          {filteredAlerts.length === 0 ? (
            <div className="no-alerts">
              <span className="material-icons">notifications_off</span>
              <p>No alerts match your filters</p>
            </div>
          ) : (
            filteredAlerts.map(alert => (
              <div key={alert.id} className={`alert-item ${getSeverityClass(alert.severity)} ${alert.status === 'resolved' ? 'resolved' : ''}`}>
                <div className="alert-icon">
                  <span className="material-icons">{getSeverityIcon(alert.severity)}</span>
                </div>
                <div className="alert-content">
                  <div className="alert-header">
                    <span className="alert-type">
                      <span className="material-icons">{getTypeIcon(alert.type)}</span>
                      {getTypeLabel(alert.type)}
                    </span>
                    <span className="alert-timestamp">{alert.timestamp}</span>
                  </div>
                  <p className="alert-message">{alert.message}</p>
                  {alert.cluster && (
                    <p className="alert-location">Location: {alert.cluster}</p>
                  )}
                </div>
                <div className="alert-actions">
                  {alert.status === 'active' ? (
                    <>
                      <button 
                        className="btn btn-sm btn-primary"
                        onClick={() => handleResolve(alert.id)}
                      >
                        Resolve
                      </button>
                      <button className="btn btn-sm btn-secondary">Details</button>
                    </>
                  ) : (
                    <span className="resolved-tag">Resolved</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Alert Settings</h3>
        </div>
        <div className="alert-settings">
          <div className="settings-section">
            <h4>Notification Preferences</h4>
            <div className="setting-item">
              <div className="setting-label">
                <span>Email Notifications</span>
                <p className="setting-description">Receive alert notifications via email</p>
              </div>
              <div className="setting-control">
                <label className="toggle-switch">
                  <input type="checkbox" checked />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
            <div className="setting-item">
              <div className="setting-label">
                <span>SMS Notifications</span>
                <p className="setting-description">Receive alert notifications via SMS</p>
              </div>
              <div className="setting-control">
                <label className="toggle-switch">
                  <input type="checkbox" />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
            <div className="setting-item">
              <div className="setting-label">
                <span>In-App Notifications</span>
                <p className="setting-description">Receive alert notifications within the app</p>
              </div>
              <div className="setting-control">
                <label className="toggle-switch">
                  <input type="checkbox" checked />
                  <span className="toggle-slider"></span>
                </label>
              </div>
            </div>
          </div>

          <div className="settings-section">
            <h4>Alert Thresholds</h4>
            <div className="setting-item">
              <div className="setting-label">
                <span>Capacity Warning Threshold</span>
                <p className="setting-description">Trigger alert when cluster capacity exceeds this percentage</p>
              </div>
              <div className="setting-control">
                <input type="range" min="50" max="100" value="85" />
                <span className="range-value">85%</span>
              </div>
            </div>
            <div className="setting-item">
              <div className="setting-label">
                <span>Shelf Life Warning</span>
                <p className="setting-description">Trigger alert when bags approach this percentage of shelf life</p>
              </div>
              <div className="setting-control">
                <input type="range" min="50" max="100" value="75" />
                <span className="range-value">75%</span>
              </div>
            </div>
            <div className="setting-item">
              <div className="setting-label">
                <span>Camera Connection Timeout</span>
                <p className="setting-description">Trigger alert when camera is unresponsive for this many seconds</p>
              </div>
              <div className="setting-control">
                <input type="range" min="5" max="60" value="15" />
                <span className="range-value">15s</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Alerts;
