import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './ClusterManagement.css';

// Configure axios to include CSRF token
axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFToken';
axios.defaults.withCredentials = true;

const ClusterManagement = () => {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    location_x: '',
    location_y: '',
    length: '',
    width: '',
    max_capacity: ''
  });
  const [showMapEditor, setShowMapEditor] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [dragStartPos, setDragStartPos] = useState({ x: 0, y: 0 });
  const [newCluster, setNewCluster] = useState(null);
  const [warehouseScale, setWarehouseScale] = useState(10); // pixels per meter
  const [warehouseDimensions, setWarehouseDimensions] = useState({ width: 1000, height: 600 });
  const [error, setError] = useState('');
  
  const warehouseRef = useRef(null);

  useEffect(() => {
    // Fetch clusters from the API
    const fetchClusters = async () => {
      try {
        setLoading(true);
        setError('');
        const response = await axios.get('/api/clusters/');
        // Ensure we're setting an array
        if (Array.isArray(response.data)) {
          setClusters(response.data);
        } else {
          console.error('API did not return an array:', response.data);
          setClusters([]); // Set to empty array if response is not an array
          setError('Invalid data format received from server');
        }
        setLoading(false);
      } catch (error) {
        console.error('Error fetching clusters:', error);
        setError('Failed to load clusters. Please refresh the page and try again.');
        setClusters([]); // Ensure clusters is an array even after error
        setLoading(false);
      }
    };

    fetchClusters();
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      setError('');
      // Create a new cluster
      const clusterData = {
        ...formData,
        location_x: parseFloat(formData.location_x),
        location_y: parseFloat(formData.location_y),
        length: parseFloat(formData.length),
        width: parseFloat(formData.width),
        max_capacity: parseInt(formData.max_capacity),
        current_count: 0 // Explicitly set initial count to 0
      };
      
      console.log('Sending cluster data:', clusterData);
      const response = await axios.post('/api/clusters/', clusterData);
      console.log('Response:', response.data);
      
      // Add the new cluster to the state
      // Ensure we're working with an array
      const currentClusters = Array.isArray(clusters) ? clusters : [];
      setClusters([...currentClusters, response.data]);
      
      // Reset form
      setShowForm(false);
      setFormData({
        name: '',
        location_x: '',
        location_y: '',
        length: '',
        width: '',
        max_capacity: ''
      });
    } catch (error) {
      console.error('Error creating cluster:', error);
      const errorMessage = error.response?.data?.detail || 
                          error.response?.data?.error || 
                          'Failed to create cluster. Please try again.';
      setError(errorMessage);
      alert(errorMessage);
    }
  };

  const handleUpdateCluster = async (e) => {
    e.preventDefault();
    
    if (!selectedCluster) return;
    
    try {
      setError('');
      // Update the selected cluster
      const clusterData = {
        ...formData,
        location_x: parseFloat(formData.location_x),
        location_y: parseFloat(formData.location_y),
        length: parseFloat(formData.length),
        width: parseFloat(formData.width),
        max_capacity: parseInt(formData.max_capacity)
      };
      
      const response = await axios.put(`/api/clusters/${selectedCluster.id}/`, clusterData);
      
      // Update clusters array - ensure we're working with an array
      if (Array.isArray(clusters)) {
        const updatedClusters = clusters.map(cluster => 
          cluster.id === selectedCluster.id ? response.data : cluster
        );
        setClusters(updatedClusters);
      } else {
        console.error('clusters is not an array:', clusters);
        setClusters([response.data]); // Reset with just the updated cluster
      }
      
      setShowForm(false);
      setSelectedCluster(null);
      setFormData({
        name: '',
        location_x: '',
        location_y: '',
        length: '',
        width: '',
        max_capacity: ''
      });
    } catch (error) {
      console.error('Error updating cluster:', error);
      const errorMessage = error.response?.data?.detail || 
                          error.response?.data?.error || 
                          'Failed to update cluster. Please try again.';
      setError(errorMessage);
      alert(errorMessage);
    }
  };

  const handleMapEditorToggle = () => {
    setShowMapEditor(!showMapEditor);
  };

  const getUtilizationClass = (percentage) => {
    if (percentage >= 90) return 'high';
    if (percentage >= 70) return 'medium';
    return 'low';
  };

  const handleAdjustCount = async (clusterId, newCount) => {
    try {
      setError('');
      const response = await axios.post(`/api/clusters/${clusterId}/adjust_count/`, {
        count: newCount
      });
      
      // Update clusters array
      if (Array.isArray(clusters)) {
        const updatedClusters = clusters.map(cluster => 
          cluster.id === clusterId ? response.data : cluster
        );
        setClusters(updatedClusters);
      } else {
        console.error('clusters is not an array:', clusters);
        setClusters([response.data]); // Reset with just the updated cluster
      }
    } catch (error) {
      console.error('Error adjusting count:', error);
      const errorMessage = error.response?.data?.detail || 
                          error.response?.data?.error || 
                          'Failed to adjust count. Please try again.';
      setError(errorMessage);
      alert(errorMessage);
    }
  };

  const handleDeleteCluster = async (clusterId) => {
    if (!window.confirm('Are you sure you want to delete this cluster?')) {
      return;
    }
    
    try {
      setError('');
      await axios.delete(`/api/clusters/${clusterId}/`);
      
      // Remove the cluster from the state
      if (Array.isArray(clusters)) {
        setClusters(clusters.filter(cluster => cluster.id !== clusterId));
      } else {
        console.error('clusters is not an array:', clusters);
        setClusters([]); // Reset to empty array
      }
    } catch (error) {
      console.error('Error deleting cluster:', error);
      const errorMessage = error.response?.data?.detail || 
                          error.response?.data?.error || 
                          'Failed to delete cluster. Please try again.';
      setError(errorMessage);
      alert(errorMessage);
    }
  };

  // Warehouse map editor functions
  const handleMapClick = (e) => {
    if (showMapEditor && !isDragging && !isResizing && !newCluster) {
      const rect = warehouseRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      // Create a new cluster at the clicked position
      setNewCluster({
        location_x: x / warehouseScale,
        location_y: y / warehouseScale,
        length: 5, // Default 5 meters
        width: 5,  // Default 5 meters
        name: `Cluster ${Array.isArray(clusters) ? clusters.length + 1 : 1}`,
        max_capacity: 100 // Default capacity
      });
      
      setIsDragging(true);
      setDragStartPos({ x, y });
    }
  };

  const handleMapMouseMove = (e) => {
    if (!showMapEditor) return;
    
    const rect = warehouseRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    if (isDragging && newCluster) {
      // If creating a new cluster, update its dimensions
      const width = Math.max(1, Math.abs(x - dragStartPos.x) / warehouseScale);
      const height = Math.max(1, Math.abs(y - dragStartPos.y) / warehouseScale);
      
      // Calculate the correct position based on drag direction
      const location_x = Math.min(dragStartPos.x, x) / warehouseScale;
      const location_y = Math.min(dragStartPos.y, y) / warehouseScale;
      
      setNewCluster({
        ...newCluster,
        location_x,
        location_y,
        length: height,
        width: width
      });
    } else if (isDragging && selectedCluster) {
      // If dragging an existing cluster, update its position
      const deltaX = (x - dragStartPos.x) / warehouseScale;
      const deltaY = (y - dragStartPos.y) / warehouseScale;
      
      setSelectedCluster({
        ...selectedCluster,
        location_x: selectedCluster.location_x + deltaX,
        location_y: selectedCluster.location_y + deltaY
      });
      
      setDragStartPos({ x, y });
    } else if (isResizing && selectedCluster) {
      // If resizing an existing cluster, update its dimensions
      const width = Math.max(1, (x - (selectedCluster.location_x * warehouseScale)) / warehouseScale);
      const height = Math.max(1, (y - (selectedCluster.location_y * warehouseScale)) / warehouseScale);
      
      setSelectedCluster({
        ...selectedCluster,
        length: height,
        width: width
      });
    }
  };

  const handleMapMouseUp = async () => {
    if (!showMapEditor) return;
    
    if (isDragging && newCluster) {
      // Add the new cluster to the form for confirmation
      setFormData({
        name: newCluster.name,
        location_x: newCluster.location_x.toFixed(2),
        location_y: newCluster.location_y.toFixed(2),
        length: newCluster.length.toFixed(2),
        width: newCluster.width.toFixed(2),
        max_capacity: newCluster.max_capacity.toString()
      });
      
      setShowForm(true);
      setNewCluster(null);
    } else if ((isDragging || isResizing) && selectedCluster) {
      // Update the cluster in the database
      try {
        setError('');
        const clusterData = {
          ...selectedCluster,
          location_x: parseFloat(selectedCluster.location_x.toFixed(2)),
          location_y: parseFloat(selectedCluster.location_y.toFixed(2)),
          length: parseFloat(selectedCluster.length.toFixed(2)),
          width: parseFloat(selectedCluster.width.toFixed(2))
        };
        
        const response = await axios.patch(`/api/clusters/${selectedCluster.id}/`, clusterData);
        
        // Update clusters array
        if (Array.isArray(clusters)) {
          const updatedClusters = clusters.map(cluster => 
            cluster.id === selectedCluster.id ? response.data : cluster
          );
          setClusters(updatedClusters);
        } else {
          console.error('clusters is not an array:', clusters);
          setClusters([response.data]); // Reset with just the updated cluster
        }
      } catch (error) {
        console.error('Error updating cluster:', error);
        // Revert changes if update fails
        const originalCluster = Array.isArray(clusters) ? clusters.find(c => c.id === selectedCluster.id) : null;
        setSelectedCluster(originalCluster);
        
        const errorMessage = error.response?.data?.detail || 
                            error.response?.data?.error || 
                            'Failed to update cluster. Please try again.';
        setError(errorMessage);
        alert(errorMessage);
      }
    }
    
    setIsDragging(false);
    setIsResizing(false);
  };

  const handleClusterClick = (e, cluster) => {
    if (showMapEditor) {
      e.stopPropagation();
      setSelectedCluster(cluster);
    }
  };

  const handleClusterDoubleClick = (e, cluster) => {
    e.stopPropagation();
    setSelectedCluster(cluster);
    setFormData({
      name: cluster.name,
      location_x: cluster.location_x.toFixed(2),
      location_y: cluster.location_y.toFixed(2),
      length: cluster.length.toFixed(2),
      width: cluster.width.toFixed(2),
      max_capacity: cluster.max_capacity.toString()
    });
    setShowForm(true);
  };

  const handleResizeStart = (e, cluster) => {
    e.stopPropagation();
    setSelectedCluster(cluster);
    setIsResizing(true);
  };

  const handleDragStart = (e, cluster) => {
    e.stopPropagation();
    
    const rect = warehouseRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    setSelectedCluster(cluster);
    setIsDragging(true);
    setDragStartPos({ x, y });
  };

  if (loading) {
    return <div className="loading">Loading clusters...</div>;
  }

  return (
    <div className="cluster-management">
      <h2>Cluster Management</h2>
      <p className="page-description">Define and manage storage clusters within the warehouse</p>

      {error && <div className="error-message">{error}</div>}

      <div className="section storage-clusters">
        <div className="section-header">
          <h3>Storage Clusters</h3>
          <div className="actions">
            <button 
              className={`map-editor-btn ${showMapEditor ? 'active' : ''}`} 
              onClick={handleMapEditorToggle}
            >
              {showMapEditor ? 'Exit Editor' : 'Map Editor'}
            </button>
            <button 
              className="add-btn"
              onClick={() => {
                setSelectedCluster(null);
                setFormData({
                  name: '',
                  location_x: '',
                  location_y: '',
                  length: '',
                  width: '',
                  max_capacity: ''
                });
                setShowForm(true);
              }}
            >
              Add New Cluster
            </button>
          </div>
        </div>

        {showMapEditor && (
          <div className="warehouse-map-container">
            <div 
              className="warehouse-map" 
              ref={warehouseRef}
              onClick={handleMapClick}
              onMouseMove={handleMapMouseMove}
              onMouseUp={handleMapMouseUp}
              onMouseLeave={handleMapMouseUp}
              style={{ 
                width: `${warehouseDimensions.width}px`, 
                height: `${warehouseDimensions.height}px` 
              }}
            >
              <div className="map-instructions">
                {isDragging || isResizing ? 
                  'Release to place cluster' : 
                  'Click and drag to create a new cluster'
                }
              </div>
              
              {/* Render existing clusters */}
              {Array.isArray(clusters) ? clusters.map(cluster => (
                <div 
                  key={cluster.id}
                  className={`cluster-box ${selectedCluster?.id === cluster.id ? 'selected' : ''} utilization-${getUtilizationClass(cluster.utilization_percentage)}`}
                  style={{
                    left: `${cluster.location_x * warehouseScale}px`,
                    top: `${cluster.location_y * warehouseScale}px`,
                    width: `${cluster.width * warehouseScale}px`,
                    height: `${cluster.length * warehouseScale}px`
                  }}
                  onClick={(e) => handleClusterClick(e, cluster)}
                  onDoubleClick={(e) => handleClusterDoubleClick(e, cluster)}
                  onMouseDown={(e) => handleDragStart(e, cluster)}
                >
                  <div className="cluster-name">{cluster.name}</div>
                  <div className="cluster-capacity">
                    {cluster.current_count}/{cluster.max_capacity} bags
                  </div>
                  <div 
                    className="resize-handle"
                    onMouseDown={(e) => handleResizeStart(e, cluster)}
                  ></div>
                </div>
              )) : <div>No clusters available</div>}
              
              {/* Render new cluster being created */}
              {newCluster && (
                <div 
                  className="cluster-box new-cluster"
                  style={{
                    left: `${newCluster.location_x * warehouseScale}px`,
                    top: `${newCluster.location_y * warehouseScale}px`,
                    width: `${newCluster.width * warehouseScale}px`,
                    height: `${newCluster.length * warehouseScale}px`
                  }}
                >
                  <div className="cluster-name">New Cluster</div>
                </div>
              )}
            </div>
            <div className="map-controls">
              <div className="scale-control">
                <label>Scale (px/m):</label>
                <input 
                  type="range" 
                  min="5" 
                  max="20" 
                  value={warehouseScale}
                  onChange={(e) => setWarehouseScale(parseInt(e.target.value))}
                />
                <span>{warehouseScale}</span>
              </div>
            </div>
          </div>
        )}

        {Array.isArray(clusters) && clusters.length === 0 && !showMapEditor ? (
          <div className="no-clusters">
            <div className="empty-state">
              <img src="/static/images/warehouse-icon.svg" alt="No clusters defined yet" />
              <p>No clusters defined yet</p>
              <p>Click "Add Cluster" to define storage areas in your warehouse</p>
            </div>
          </div>
        ) : !showMapEditor && (
          <div className="clusters-table">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Dimensions</th>
                  <th>Capacity</th>
                  <th>Utilization</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {Array.isArray(clusters) ? clusters.map(cluster => (
                  <tr key={cluster.id}>
                    <td>{cluster.name}</td>
                    <td>({cluster.location_x.toFixed(1)}, {cluster.location_y.toFixed(1)})</td>
                    <td>{cluster.length.toFixed(1)}m × {cluster.width.toFixed(1)}m</td>
                    <td>
                      <div className="capacity-display">
                        <span>{cluster.current_count}/{cluster.max_capacity} bags</span>
                        <div className="manual-adjust">
                          <button 
                            onClick={() => {
                              const newCount = prompt('Enter new bag count:', cluster.current_count);
                              if (newCount !== null) {
                                handleAdjustCount(cluster.id, parseInt(newCount));
                              }
                            }}
                          >
                            Adjust
                          </button>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div className={`utilization-bar utilization-${getUtilizationClass(cluster.utilization_percentage)}`}>
                        <div 
                          className="fill" 
                          style={{ width: `${Math.min(100, cluster.utilization_percentage)}%` }}
                        ></div>
                        <span>{cluster.utilization_percentage.toFixed(1)}%</span>
                      </div>
                    </td>
                    <td>
                      <div className="action-buttons">
                        <button 
                          className="edit-btn"
                          onClick={() => {
                            setSelectedCluster(cluster);
                            setFormData({
                              name: cluster.name,
                              location_x: cluster.location_x.toFixed(2),
                              location_y: cluster.location_y.toFixed(2),
                              length: cluster.length.toFixed(2),
                              width: cluster.width.toFixed(2),
                              max_capacity: cluster.max_capacity.toString()
                            });
                            setShowForm(true);
                          }}
                        >
                          Edit
                        </button>
                        <button 
                          className="delete-btn"
                          onClick={() => handleDeleteCluster(cluster.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                )) : <tr><td colSpan="6">No clusters available</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="section warehouse-overview">
        <h3>Warehouse Overview</h3>
        <div className="warehouse-stats">
          <div className="stat-card">
            <div className="stat-title">Total Clusters</div>
            <div className="stat-value">{Array.isArray(clusters) ? clusters.length : 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-title">Total Capacity</div>
            <div className="stat-value">
              {Array.isArray(clusters) ? 
                clusters.reduce((sum, cluster) => sum + cluster.max_capacity, 0) : 0}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-title">Current Inventory</div>
            <div className="stat-value">
              {Array.isArray(clusters) ? 
                clusters.reduce((sum, cluster) => sum + cluster.current_count, 0) : 0}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-title">Overall Utilization</div>
            <div className="stat-value">
              {!Array.isArray(clusters) || clusters.length === 0 ? '0%' : 
                (clusters.reduce((sum, cluster) => sum + cluster.current_count, 0) / 
                clusters.reduce((sum, cluster) => sum + cluster.max_capacity, 0) * 100).toFixed(1) + '%'
              }
            </div>
          </div>
        </div>
      </div>

      {/* Cluster form modal */}
      {showForm && (
        <div className="modal">
          <div className="modal-content">
            <div className="modal-header">
              <h3>{selectedCluster ? 'Edit Cluster' : 'Add New Cluster'}</h3>
              <button className="close-btn" onClick={() => setShowForm(false)}>×</button>
            </div>
            <form onSubmit={selectedCluster ? handleUpdateCluster : handleSubmit}>
              <div className="form-group">
                <label htmlFor="name">Name</label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleInputChange}
                  required
                />
              </div>
              
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="location_x">X Coordinate (m)</label>
                  <input
                    type="number"
                    id="location_x"
                    name="location_x"
                    value={formData.location_x}
                    onChange={handleInputChange}
                    step="0.1"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="location_y">Y Coordinate (m)</label>
                  <input
                    type="number"
                    id="location_y"
                    name="location_y"
                    value={formData.location_y}
                    onChange={handleInputChange}
                    step="0.1"
                    required
                  />
                </div>
              </div>
              
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="length">Length (m)</label>
                  <input
                    type="number"
                    id="length"
                    name="length"
                    value={formData.length}
                    onChange={handleInputChange}
                    step="0.1"
                    min="0.1"
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="width">Width (m)</label>
                  <input
                    type="number"
                    id="width"
                    name="width"
                    value={formData.width}
                    onChange={handleInputChange}
                    step="0.1"
                    min="0.1"
                    required
                  />
                </div>
              </div>
              
              <div className="form-group">
                <label htmlFor="max_capacity">Maximum Capacity (bags)</label>
                <input
                  type="number"
                  id="max_capacity"
                  name="max_capacity"
                  value={formData.max_capacity}
                  onChange={handleInputChange}
                  min="1"
                  required
                />
              </div>
              
              <div className="form-actions">
                <button type="button" className="cancel-btn" onClick={() => setShowForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="submit-btn">
                  {selectedCluster ? 'Update Cluster' : 'Save Cluster'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClusterManagement;
