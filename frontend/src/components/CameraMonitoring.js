import React, { useState, useEffect } from 'react';
import axios from 'axios';
import HikvisionStreamViewer from './HikvisionStreamViewer';

const CameraMonitoring = () => {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showHikvisionForm, setShowHikvisionForm] = useState(false);
  const [showCalibrationForm, setShowCalibrationForm] = useState(false);
  const [newCamera, setNewCamera] = useState({
    name: '',
    location_description: '',
    rtsp_url: '',
    resolution: '1280x720',
    fps: 15,
    coverage_clusters: []
  });
  const [hikvisionCamera, setHikvisionCamera] = useState({
    ip_address: '',
    username: 'admin',
    password: '',
    port: 80,
    add_all_cameras: true,
    codec: 'auto'
  });
  const [hikvisionStatus, setHikvisionStatus] = useState('');
  const [hikvisionError, setHikvisionError] = useState('');
  const [calibrationData, setCalibrationData] = useState({
    camera_id: '',
    reference_points: '',
    scale_factor: 1.0,
    rotation_angle: 0,
    notes: ''
  });
  const [clusters, setClusters] = useState([]);
  const [calibrationStatus, setCalibrationStatus] = useState('');
  const [calibrationError, setCalibrationError] = useState('');

  // Fetch clusters for camera coverage selection
  const fetchClusters = async () => {
    try {
      const response = await axios.get('/api/camera/clusters/');
      setClusters(response.data);
    } catch (error) {
      console.error('Error fetching clusters:', error);
    }
  };

  // Fetch cameras from the database
  const fetchCameras = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/camera/cameras/');
      
      // Ensure response.data is an array
      const cameraArray = Array.isArray(response.data) ? response.data : (response.data.results || []);
      setCameras(cameraArray);
      
      // Select the first camera by default if none is selected
      if (cameraArray.length > 0 && !selectedCamera) {
        setSelectedCamera(cameraArray[0]);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching cameras:', error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClusters();
    fetchCameras();
  }, []);

  const handleCameraSelect = (camera) => {
    setSelectedCamera(camera);
    // Reset calibration form when selecting a different camera
    if (calibrationData.camera_id !== camera.id) {
      setCalibrationData({
        camera_id: camera.id,
        reference_points: '',
        scale_factor: 1.0,
        rotation_angle: 0,
        notes: ''
      });
    }
    setShowCalibrationForm(false);
    setCalibrationStatus('');
    setCalibrationError('');
  };

  const handleNewCameraChange = (e) => {
    const { name, value } = e.target;
    setNewCamera({
      ...newCamera,
      [name]: value
    });
  };

  const handleClusterSelection = (e) => {
    const options = e.target.options;
    const selectedClusters = [];
    for (let i = 0; i < options.length; i++) {
      if (options[i].selected) {
        selectedClusters.push(parseInt(options[i].value));
      }
    }
    setNewCamera({
      ...newCamera,
      coverage_clusters: selectedClusters
    });
  };

  const handleCalibrationChange = (e) => {
    const { name, value } = e.target;
    setCalibrationData({
      ...calibrationData,
      [name]: value
    });
  };

  const handleAddCamera = async (e) => {
    e.preventDefault();
    
    try {
      // Prepare camera data for API
      const cameraData = {
        name: newCamera.name,
        location_description: newCamera.location_description,
        rtsp_url: newCamera.rtsp_url,
        resolution_width: parseInt(newCamera.resolution.split('x')[0]),
        resolution_height: parseInt(newCamera.resolution.split('x')[1]),
        fps: parseInt(newCamera.fps),
        coverage_clusters: newCamera.coverage_clusters
      };
      
      // Send to API
      setLoading(true);
      const response = await axios.post('/api/camera/cameras/', cameraData);
      
      if (response.status === 201) {
        // Camera created successfully
        // Fetch the updated camera list
        await fetchCameras();
        
        // Reset form
        setNewCamera({
          name: '',
          location_description: '',
          rtsp_url: '',
          resolution: '1280x720',
          fps: 15,
          coverage_clusters: []
        });
        
        setShowAddForm(false);
        
        // Select the newly added camera
        setSelectedCamera(response.data);
      }
    } catch (error) {
      console.error('Error adding camera:', error);
      alert(`Failed to add camera: ${error.response?.data?.detail || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleHikvisionCameraChange = (e) => {
    const { name, value, type, checked } = e.target;
    setHikvisionCamera({
      ...hikvisionCamera,
      [name]: type === 'checkbox' ? checked : value
    });
  };

  const handleAddHikvisionCamera = async (e) => {
    e.preventDefault();
    
    // Reset status
    setHikvisionStatus('');
    setHikvisionError('');
    
    try {
      // Validate inputs
      if (!hikvisionCamera.ip_address) {
        setHikvisionError('IP Address is required');
        return;
      }
      
      setHikvisionStatus('Connecting to Hikvision device...');
      
      // Send request to backend
      const response = await axios.post('/api/camera/cameras/add_hikvision_camera/', {
        ip_address: hikvisionCamera.ip_address,
        username: hikvisionCamera.username,
        password: hikvisionCamera.password,
        port: parseInt(hikvisionCamera.port),
        add_all_cameras: hikvisionCamera.add_all_cameras,
        codec: hikvisionCamera.codec
      });
      
      if (response.data.status === 'success') {
        setHikvisionStatus(`Successfully added ${response.data.cameras.length} cameras`);
        
        // Refresh camera list
        await fetchCameras();
        
        // Reset form after a delay
        setTimeout(() => {
          setHikvisionCamera({
            ip_address: '',
            username: 'admin',
            password: '',
            port: 80,
            add_all_cameras: true,
            codec: 'auto'
          });
          setShowHikvisionForm(false);
          setHikvisionStatus('');
        }, 2000);
      } else {
        setHikvisionError(response.data.message || 'Failed to add cameras');
      }
    } catch (error) {
      console.error('Error adding Hikvision camera:', error);
      setHikvisionError(error.response?.data?.message || 'Connection failed');
    }
  };

  const handleCameraActivation = () => {
    if (!selectedCamera) return;
    
    // Update camera status
    const updatedCameras = cameras.map(camera => 
      camera.id === selectedCamera.id 
        ? { ...camera, status: camera.status === 'active' ? 'inactive' : 'active' } 
        : camera
    );
    
    setCameras(updatedCameras);
    
    // Update selected camera
    setSelectedCamera({
      ...selectedCamera,
      status: selectedCamera.status === 'active' ? 'inactive' : 'active'
    });
  };

  const handleCalibration = (e) => {
    e.preventDefault();
    
    // Simulate calibration process
    setCalibrationStatus('Calibrating camera...');
    
    // In a real app, this would be an API call
    setTimeout(() => {
      if (Math.random() > 0.2) { // 80% success rate for demo
        setCalibrationStatus('Calibration successful! Camera is ready for detection.');
        setCalibrationError('');
        
        // Update camera with calibration data
        const updatedCameras = cameras.map(camera => 
          camera.id === selectedCamera.id 
            ? { ...camera, calibrated: true } 
            : camera
        );
        
        setCameras(updatedCameras);
        setSelectedCamera({
          ...selectedCamera,
          calibrated: true
        });
        
        // Hide calibration form after success
        setTimeout(() => {
          setShowCalibrationForm(false);
        }, 2000);
      } else {
        setCalibrationStatus('');
        setCalibrationError('Calibration failed. Please check reference points and try again.');
      }
    }, 2000);
  };

  const handleTestConnection = () => {
    if (!selectedCamera) return;
    
    setCalibrationStatus('Testing connection to RTSP stream...');
    setCalibrationError('');
    
    // In a real app, this would be an API call to test the connection
    setTimeout(() => {
      if (selectedCamera.rtsp_url && selectedCamera.rtsp_url.startsWith('rtsp://')) {
        setCalibrationStatus('Connection successful! Stream is accessible.');
      } else {
        setCalibrationError('Connection failed. Please check the RTSP URL and try again.');
        setCalibrationStatus('');
      }
    }, 1500);
  };

  const getStatusClass = (status) => {
    switch (status) {
      case 'active':
        return 'status-active';
      case 'inactive':
        return 'status-inactive';
      case 'error':
        return 'status-error';
      default:
        return '';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active':
        return 'check_circle';
      case 'inactive':
        return 'pause_circle';
      case 'error':
        return 'error';
      default:
        return 'help';
    }
  };

  if (loading) {
    return <div className="loading">Loading cameras...</div>;
  }

  return (
    <div className="camera-monitoring">
      <h2>Camera Monitoring</h2>
      <p className="page-description">Monitor and manage RTSP camera feeds for cement bag tracking</p>

      <div className="camera-grid">
        <div className="card camera-list">
          <div className="card-header">
            <h3 className="card-title">Cameras</h3>
            <div className="button-group">
              <button 
                className="btn btn-secondary"
                onClick={() => {
                  setShowHikvisionForm(!showHikvisionForm);
                  setShowAddForm(false);
                }}
              >
                {showHikvisionForm ? 'Cancel' : 'Add Hikvision'}
              </button>
              <button 
                className="btn btn-primary"
                onClick={() => {
                  setShowAddForm(!showAddForm);
                  setShowHikvisionForm(false);
                }}
              >
                {showAddForm ? 'Cancel' : 'Add Camera'}
              </button>
            </div>
          </div>
          
          {showHikvisionForm && (
            <div className="add-camera-form hikvision-form">
              <h4>Add Hikvision Camera</h4>
              {hikvisionStatus && (
                <div className="hikvision-status success">
                  <span className="material-icons">info</span>
                  {hikvisionStatus}
                </div>
              )}
              {hikvisionError && (
                <div className="hikvision-status error">
                  <span className="material-icons">error</span>
                  {hikvisionError}
                </div>
              )}
              <form onSubmit={handleAddHikvisionCamera}>
                <div className="form-group">
                  <label className="form-label">IP Address</label>
                  <input
                    type="text"
                    name="ip_address"
                    className="form-control"
                    value={hikvisionCamera.ip_address}
                    onChange={handleHikvisionCameraChange}
                    placeholder="192.168.1.100"
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Username</label>
                    <input
                      type="text"
                      name="username"
                      className="form-control"
                      value={hikvisionCamera.username}
                      onChange={handleHikvisionCameraChange}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Password</label>
                    <input
                      type="password"
                      name="password"
                      className="form-control"
                      value={hikvisionCamera.password}
                      onChange={handleHikvisionCameraChange}
                      required
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Port</label>
                    <input
                      type="number"
                      name="port"
                      className="form-control"
                      value={hikvisionCamera.port}
                      onChange={handleHikvisionCameraChange}
                      min="1"
                      max="65535"
                      required
                    />
                  </div>
                  <div className="form-group checkbox-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        name="add_all_cameras"
                        checked={hikvisionCamera.add_all_cameras}
                        onChange={handleHikvisionCameraChange}
                      />
                      Add all cameras from NVR
                    </label>
                  </div>
                </div>
                <div className="form-actions">
                  <button type="submit" className="btn btn-primary">Add Hikvision Camera</button>
                </div>
              </form>
            </div>
          )}
          
          {showAddForm && (
            <div className="add-camera-form">
              <h4>Add New Camera</h4>
              <form onSubmit={handleAddCamera}>
                <div className="form-group">
                  <label className="form-label">Camera Name</label>
                  <input
                    type="text"
                    name="name"
                    className="form-control"
                    value={newCamera.name}
                    onChange={handleNewCameraChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Location Description</label>
                  <input
                    type="text"
                    name="location_description"
                    className="form-control"
                    value={newCamera.location_description}
                    onChange={handleNewCameraChange}
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">RTSP URL</label>
                  <input
                    type="text"
                    name="rtsp_url"
                    className="form-control"
                    value={newCamera.rtsp_url}
                    onChange={handleNewCameraChange}
                    placeholder="rtsp://example.com/stream"
                    required
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Resolution</label>
                    <select
                      name="resolution"
                      className="form-control"
                      value={newCamera.resolution}
                      onChange={handleNewCameraChange}
                    >
                      <option value="640x480">640x480</option>
                      <option value="1280x720">1280x720 (HD)</option>
                      <option value="1920x1080">1920x1080 (Full HD)</option>
                      <option value="3840x2160">3840x2160 (4K)</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Frame Rate (FPS)</label>
                    <input
                      type="number"
                      name="fps"
                      className="form-control"
                      value={newCamera.fps}
                      onChange={handleNewCameraChange}
                      min="1"
                      max="60"
                      required
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">Coverage Clusters</label>
                  <select
                    multiple
                    name="coverage_clusters"
                    className="form-control"
                    onChange={handleClusterSelection}
                    size={Math.min(5, clusters.length)}
                  >
                    {clusters.map(cluster => (
                      <option key={cluster.id} value={cluster.id}>
                        {cluster.name}
                      </option>
                    ))}
                  </select>
                  <small className="form-text">Hold Ctrl/Cmd to select multiple clusters</small>
                </div>
                <div className="form-actions">
                  <button type="submit" className="btn btn-primary">Add Camera</button>
                </div>
              </form>
            </div>
          )}
          
          <div className="camera-items">
            {cameras.length === 0 ? (
              <div className="no-cameras">
                <span className="material-icons">videocam_off</span>
                <p>No cameras added yet</p>
                <p>Click "Add Camera" to get started</p>
              </div>
            ) : (
              cameras.map(camera => (
                <div 
                  key={camera.id} 
                  className={`camera-item ${selectedCamera && selectedCamera.id === camera.id ? 'selected' : ''}`}
                  onClick={() => handleCameraSelect(camera)}
                >
                  <div className="camera-item-header">
                    <span className="camera-name">{camera.name}</span>
                    <span className={`camera-status ${getStatusClass(camera.status)}`}>
                      <span className="material-icons">{getStatusIcon(camera.status)}</span>
                    </span>
                  </div>
                  <div className="camera-item-details">
                    <p>{camera.location_description}</p>
                    <p className="camera-specs">{camera.resolution} @ {camera.fps}fps</p>
                    {camera.calibrated && (
                      <span className="calibrated-badge">
                        <span className="material-icons">check</span>
                        Calibrated
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card camera-view">
          {selectedCamera ? (
            <>
              <div className="card-header">
                <h3 className="card-title">{selectedCamera.name} - {selectedCamera.location_description}</h3>
                <div className="camera-controls">
                  <button 
                    className="btn btn-secondary"
                    onClick={() => setShowCalibrationForm(!showCalibrationForm)}
                  >
                    {showCalibrationForm ? 'Cancel' : 'Calibrate'}
                  </button>
                  <button 
                    className="btn btn-primary"
                    onClick={handleCameraActivation}
                  >
                    {selectedCamera.status === 'active' ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              </div>
              
              {showCalibrationForm ? (
                <div className="calibration-form">
                  <h4>Camera Calibration</h4>
                  {calibrationStatus && (
                    <div className="calibration-status success">
                      <span className="material-icons">info</span>
                      {calibrationStatus}
                    </div>
                  )}
                  {calibrationError && (
                    <div className="calibration-status error">
                      <span className="material-icons">error</span>
                      {calibrationError}
                    </div>
                  )}
                  <form onSubmit={handleCalibration}>
                    <div className="form-group">
                      <label className="form-label">Reference Points (x,y coordinates)</label>
                      <textarea
                        name="reference_points"
                        className="form-control"
                        value={calibrationData.reference_points}
                        onChange={handleCalibrationChange}
                        placeholder="Format: x1,y1;x2,y2;x3,y3;x4,y4"
                        rows={3}
                        required
                      ></textarea>
                      <small className="form-text">Enter at least 4 reference points as x,y coordinates separated by semicolons</small>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label className="form-label">Scale Factor</label>
                        <input
                          type="number"
                          name="scale_factor"
                          className="form-control"
                          value={calibrationData.scale_factor}
                          onChange={handleCalibrationChange}
                          step="0.1"
                          min="0.1"
                          max="10"
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Rotation Angle (degrees)</label>
                        <input
                          type="number"
                          name="rotation_angle"
                          className="form-control"
                          value={calibrationData.rotation_angle}
                          onChange={handleCalibrationChange}
                          min="-180"
                          max="180"
                        />
                      </div>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Calibration Notes</label>
                      <textarea
                        name="notes"
                        className="form-control"
                        value={calibrationData.notes}
                        onChange={handleCalibrationChange}
                        rows={2}
                      ></textarea>
                    </div>
                    <div className="form-actions">
                      <button 
                        type="button" 
                        className="btn btn-secondary"
                        onClick={handleTestConnection}
                      >
                        Test Connection
                      </button>
                      <button type="submit" className="btn btn-primary">Calibrate Camera</button>
                    </div>
                  </form>
                </div>
              ) : (
                <>
                  <div className="camera-stream">
                    {selectedCamera.status === 'active' && selectedCamera.rtsp_url ? (
                      <HikvisionStreamViewer
                        rtspUrl={selectedCamera.rtsp_url}
                        cameraName={selectedCamera.name}
                      />
                    ) : (
                      <div className="stream-placeholder">
                        <span className="material-icons">videocam_off</span>
                        <p>Stream not available</p>
                        <small>Camera is {selectedCamera.status === 'active' ? 'active but missing RTSP URL' : 'inactive'}</small>
                      </div>
                    )}
                    
                    {/* Add instructions for connecting to the RTSP stream */}
                    <div className="rtsp-instructions">
                      <h4>About this camera feed:</h4>
                      <p>This feed is using our RTSP proxy to display the Hikvision camera stream in your browser.</p>
                      <p>The stream is refreshed every second to provide near real-time monitoring.</p>
                      <p>For better performance, consider using fewer active cameras at once.</p>
                    </div>
                  </div>
                  <div className="camera-details">
                    <div className="detail-group">
                      <h4>Status</h4>
                      <p className={getStatusClass(selectedCamera.status)}>
                        <span className="material-icons">{getStatusIcon(selectedCamera.status)}</span>
                        {selectedCamera.status.charAt(0).toUpperCase() + selectedCamera.status.slice(1)}
                      </p>
                    </div>
                    <div className="detail-group">
                      <h4>Resolution</h4>
                      <p>{selectedCamera.resolution}</p>
                    </div>
                    <div className="detail-group">
                      <h4>Frame Rate</h4>
                      <p>{selectedCamera.fps} fps</p>
                    </div>
                    <div className="detail-group">
                      <h4>Calibration</h4>
                      <p>{selectedCamera.calibrated 
                        ? <span className="status-active"><span className="material-icons">check_circle</span> Calibrated</span> 
                        : <span className="status-inactive"><span className="material-icons">pending</span> Not Calibrated</span>}</p>
                    </div>
                    <div className="detail-group">
                      <h4>Coverage</h4>
                      <div className="coverage-clusters">
                        {selectedCamera.coverage_clusters && selectedCamera.coverage_clusters.length > 0 ? (
                          selectedCamera.coverage_clusters.map((cluster, index) => (
                            <span key={index} className="cluster-badge">{cluster}</span>
                          ))
                        ) : (
                          <span className="text-muted">No clusters assigned</span>
                        )}
                      </div>
                    </div>
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="no-camera-selected">
              <span className="material-icons">videocam_off</span>
              <p>Select a camera to view its feed and details</p>
              <p>Or add a new camera to get started</p>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Recent Detection Events</h3>
          <button className="btn btn-primary">View All</button>
        </div>
        {cameras.length === 0 ? (
          <div className="no-data">
            <span className="material-icons">event_busy</span>
            <p>No detection events yet</p>
            <p>Add and calibrate cameras to start detecting cement bags</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Camera</th>
                <th>Event Type</th>
                <th>Confidence</th>
                <th>Processed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {selectedCamera && selectedCamera.status === 'active' && selectedCamera.calibrated ? (
                <>
                  <tr>
                    <td colSpan="6" className="text-center">
                      <span className="material-icons">sensors</span> Monitoring active. Events will appear here when detected.
                    </td>
                  </tr>
                </>
              ) : (
                <tr>
                  <td colSpan="6" className="text-center">
                    No events to display. Activate and calibrate a camera to start detection.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default CameraMonitoring;
