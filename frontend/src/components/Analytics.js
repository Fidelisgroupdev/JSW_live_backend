import React, { useState, useEffect } from 'react';
import axios from 'axios';

const Analytics = () => {
  const [loading, setLoading] = useState(true);
  const [inventoryData, setInventoryData] = useState({
    totalBags: 0,
    availableBags: 0,
    reservedBags: 0,
    soldBags: 0,
    damagedBags: 0,
    averageAge: 0,
    fifoComplianceRate: 0
  });
  const [movementData, setMovementData] = useState({
    dailyMovements: [],
    weeklyMovements: []
  });
  const [clusterUtilization, setClusterUtilization] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [timeRange, setTimeRange] = useState('week');

  useEffect(() => {
    // In a real application, we would fetch data from the API
    // For this demo, we'll use mock data
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Mock inventory summary data
        setInventoryData({
          totalBags: 1250,
          availableBags: 875,
          reservedBags: 220,
          soldBags: 125,
          damagedBags: 30,
          averageAge: 42,
          fifoComplianceRate: 87.5
        });
        
        // Mock movement data
        setMovementData({
          dailyMovements: [
            { date: '2025-04-01', inbound: 45, outbound: 38, internal: 12 },
            { date: '2025-04-02', inbound: 52, outbound: 41, internal: 15 },
            { date: '2025-04-03', inbound: 48, outbound: 43, internal: 10 },
            { date: '2025-04-04', inbound: 60, outbound: 52, internal: 18 },
            { date: '2025-04-05', inbound: 35, outbound: 30, internal: 8 },
            { date: '2025-04-06', inbound: 25, outbound: 22, internal: 5 },
            { date: '2025-04-07', inbound: 55, outbound: 48, internal: 20 }
          ],
          weeklyMovements: [
            { week: 'Week 1', inbound: 320, outbound: 280, internal: 85 },
            { week: 'Week 2', inbound: 345, outbound: 310, internal: 90 },
            { week: 'Week 3', inbound: 380, outbound: 350, internal: 100 },
            { week: 'Week 4', inbound: 420, outbound: 390, internal: 110 }
          ]
        });
        
        // Mock cluster utilization data
        setClusterUtilization([
          { name: 'Cluster A', capacity: 300, current: 275, percentage: 91.7 },
          { name: 'Cluster B', capacity: 250, current: 210, percentage: 84.0 },
          { name: 'Cluster C', capacity: 200, current: 150, percentage: 75.0 },
          { name: 'Cluster D', capacity: 350, current: 180, percentage: 51.4 },
          { name: 'Cluster E', capacity: 150, current: 60, percentage: 40.0 }
        ]);
        
        // Mock alerts data
        setAlerts([
          { id: 1, type: 'fifo_violation', message: 'FIFO violation detected in Cluster A', timestamp: '2025-04-07 09:15:22', severity: 'high' },
          { id: 2, type: 'capacity_warning', message: 'Cluster A approaching maximum capacity (91.7%)', timestamp: '2025-04-07 10:30:45', severity: 'medium' },
          { id: 3, type: 'shelf_life', message: '25 bags in Cluster B approaching shelf life limit', timestamp: '2025-04-06 14:22:10', severity: 'high' },
          { id: 4, type: 'camera_issue', message: 'Camera 2 connection unstable', timestamp: '2025-04-06 08:45:33', severity: 'low' },
          { id: 5, type: 'movement_anomaly', message: 'Unusual movement pattern detected in Cluster C', timestamp: '2025-04-05 16:10:05', severity: 'medium' }
        ]);
        
        setLoading(false);
      } catch (error) {
        console.error('Error fetching analytics data:', error);
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const getUtilizationClass = (percentage) => {
    if (percentage >= 90) return 'high';
    if (percentage >= 70) return 'medium';
    return 'low';
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

  if (loading) {
    return <div className="loading">Loading analytics data...</div>;
  }

  return (
    <div className="analytics">
      <h2>Analytics & Reporting</h2>
      <p className="page-description">View inventory metrics, movement analytics, and FIFO compliance reports</p>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-icon">
            <span className="material-icons">inventory_2</span>
          </div>
          <div className="metric-content">
            <h3 className="metric-title">Total Bags</h3>
            <p className="metric-value">{inventoryData.totalBags}</p>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">
            <span className="material-icons">check_circle</span>
          </div>
          <div className="metric-content">
            <h3 className="metric-title">Available</h3>
            <p className="metric-value">{inventoryData.availableBags}</p>
            <p className="metric-subtext">{((inventoryData.availableBags / inventoryData.totalBags) * 100).toFixed(1)}%</p>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">
            <span className="material-icons">schedule</span>
          </div>
          <div className="metric-content">
            <h3 className="metric-title">Reserved</h3>
            <p className="metric-value">{inventoryData.reservedBags}</p>
            <p className="metric-subtext">{((inventoryData.reservedBags / inventoryData.totalBags) * 100).toFixed(1)}%</p>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">
            <span className="material-icons">local_shipping</span>
          </div>
          <div className="metric-content">
            <h3 className="metric-title">Sold</h3>
            <p className="metric-value">{inventoryData.soldBags}</p>
            <p className="metric-subtext">{((inventoryData.soldBags / inventoryData.totalBags) * 100).toFixed(1)}%</p>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">
            <span className="material-icons">calendar_today</span>
          </div>
          <div className="metric-content">
            <h3 className="metric-title">Avg. Age</h3>
            <p className="metric-value">{inventoryData.averageAge} days</p>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-icon">
            <span className="material-icons">swap_vert</span>
          </div>
          <div className="metric-content">
            <h3 className="metric-title">FIFO Compliance</h3>
            <p className="metric-value">{inventoryData.fifoComplianceRate}%</p>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Bag Movements</h3>
          <div className="time-range-selector">
            <button 
              className={`btn btn-sm ${timeRange === 'day' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setTimeRange('day')}
            >
              Daily
            </button>
            <button 
              className={`btn btn-sm ${timeRange === 'week' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setTimeRange('week')}
            >
              Weekly
            </button>
          </div>
        </div>
        <div className="chart-container">
          <div className="chart-placeholder">
            <span className="material-icons">insert_chart</span>
            <p>Movement chart would be displayed here in a real application</p>
            <p className="chart-data-preview">
              {timeRange === 'day' ? 
                'Daily data: ' + movementData.dailyMovements.map(d => `${d.date}: ${d.inbound} in, ${d.outbound} out`).join(' | ') :
                'Weekly data: ' + movementData.weeklyMovements.map(w => `${w.week}: ${w.inbound} in, ${w.outbound} out`).join(' | ')
              }
            </p>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Cluster Utilization</h3>
          <button className="btn btn-primary">Export Report</button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Cluster</th>
              <th>Capacity</th>
              <th>Current</th>
              <th>Utilization</th>
            </tr>
          </thead>
          <tbody>
            {clusterUtilization.map((cluster, index) => (
              <tr key={index}>
                <td>{cluster.name}</td>
                <td>{cluster.capacity}</td>
                <td>{cluster.current}</td>
                <td>
                  <div className="utilization-bar">
                    <div 
                      className={`utilization-fill ${getUtilizationClass(cluster.percentage)}`}
                      style={{ width: `${cluster.percentage}%` }}
                    ></div>
                    <span className="utilization-text">{cluster.percentage.toFixed(1)}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recent Alerts</h3>
          <button className="btn btn-primary">View All</button>
        </div>
        <div className="alerts-list">
          {alerts.map(alert => (
            <div key={alert.id} className={`alert-item ${getSeverityClass(alert.severity)}`}>
              <div className="alert-icon">
                <span className="material-icons">{getSeverityIcon(alert.severity)}</span>
              </div>
              <div className="alert-content">
                <p className="alert-message">{alert.message}</p>
                <p className="alert-timestamp">{alert.timestamp}</p>
              </div>
              <div className="alert-actions">
                <button className="btn btn-sm btn-primary">Resolve</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">FIFO Compliance Report</h3>
          <button className="btn btn-primary">Generate Report</button>
        </div>
        <div className="fifo-report">
          <div className="fifo-chart-placeholder">
            <span className="material-icons">pie_chart</span>
            <p>FIFO compliance chart would be displayed here in a real application</p>
          </div>
          <div className="fifo-stats">
            <div className="fifo-stat-item">
              <h4>Overall Compliance</h4>
              <p className="fifo-stat-value">{inventoryData.fifoComplianceRate}%</p>
            </div>
            <div className="fifo-stat-item">
              <h4>Violations</h4>
              <p className="fifo-stat-value">15</p>
            </div>
            <div className="fifo-stat-item">
              <h4>Oldest Bag</h4>
              <p className="fifo-stat-value">76 days</p>
            </div>
            <div className="fifo-stat-item">
              <h4>Shelf Life Alerts</h4>
              <p className="fifo-stat-value">25</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
