import React, { useState, useEffect, useRef } from 'react';
import './CameraMonitor.css';

const CameraMonitor = () => {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeCamera, setActiveCamera] = useState(null);
  const [cameraStatus, setCameraStatus] = useState({});
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [config, setConfig] = useState({
    hardware_acceleration: true,
    low_latency: true,
    transport: 'tcp',
    buffer_size: 5,
    codec: 'auto' // Added codec option with default 'auto'
  });
  const statusInterval = useRef(null);
  const imgRef = useRef(null);
  const frameInterval = useRef(null);

  // Fetch cameras on component mount
  useEffect(() => {
    fetchCameras();
    return () => {
      // Clean up intervals on unmount
      if (statusInterval.current) {
        clearInterval(statusInterval.current);
      }
      if (frameInterval.current) {
        clearInterval(frameInterval.current);
      }
    };
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps
  // We intentionally only want this to run once on mount

  // Start status polling when cameras are loaded
  useEffect(() => {
    if (cameras.length > 0 && !statusInterval.current) {
      statusInterval.current = setInterval(fetchAllCameraStatus, 5000);
      fetchAllCameraStatus(); // Initial fetch
    }
    return () => {
      if (statusInterval.current) {
        clearInterval(statusInterval.current);
        statusInterval.current = null;
      }
    };
  }, [cameras]);

  // Fetch camera frames when active camera changes
  useEffect(() => {
    if (frameInterval.current) {
      clearInterval(frameInterval.current);
      frameInterval.current = null;
    }

    if (activeCamera) {
      // Auto-detect likely codec based on channel number for Hikvision cameras
      if (config.codec === 'auto' && activeCamera.rtsp_url) {
        const url = activeCamera.rtsp_url.toLowerCase();
        // Check if it's a Hikvision camera URL
        if (url.includes('hikvision') || url.includes('isapi')) {
          // Check for H.265 channels (typically 401, 402, etc.)
          if (url.includes('ch=4') || url.includes('/channels/4')) {
            setConfig(prev => ({ ...prev, codec: 'h265' }));
          } else if (url.includes('ch=1') || url.includes('/channels/1')) {
            setConfig(prev => ({ ...prev, codec: 'h264' }));
          }
        }
      }
      
      fetchCameraFrame(activeCamera.id);
      frameInterval.current = setInterval(() => {
        fetchCameraFrame(activeCamera.id);
      }, 100); // 10 FPS
    }

    return () => {
      if (frameInterval.current) {
        clearInterval(frameInterval.current);
        frameInterval.current = null;
      }
    };
  }, [activeCamera, config.codec]);

  const fetchCameras = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/camera/cameras/');
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      const data = await response.json();
      
      // Ensure data is an array
      const cameraArray = Array.isArray(data) ? data : data.results || [];
      setCameras(cameraArray);
      
      // Set first camera as active if available
      if (cameraArray.length > 0 && !activeCamera) {
        setActiveCamera(cameraArray[0]);
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error fetching cameras:', error);
      setError('Failed to load cameras. Please try again later.');
      setLoading(false);
    }
  };

  const fetchAllCameraStatus = async () => {
    try {
      const response = await fetch('/api/camera/monitor/status/');
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      const data = await response.json();
      if (data.success) {
        setCameraStatus(data.status);
      }
    } catch (error) {
      console.error('Error fetching camera status:', error);
    }
  };

  const fetchCameraFrame = async (cameraId) => {
    if (!imgRef.current) return;
    
    try {
      // Use base64 for React component
      const response = await fetch(`/api/camera/monitor/frame/${cameraId}/?base64=true`);
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success && data.frame) {
        imgRef.current.src = `data:image/jpeg;base64,${data.frame}`;
      }
    } catch (error) {
      console.error('Error fetching camera frame:', error);
    }
  };

  const startCamera = async (cameraId) => {
    try {
      const response = await fetch('/api/camera/monitor/start/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          camera_id: cameraId,
          config: config
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success) {
        // Update camera status
        setCameraStatus(prev => ({
          ...prev,
          [cameraId]: {
            ...prev[cameraId],
            status: {
              ...prev[cameraId]?.status,
              status: 'connecting'
            }
          }
        }));
        
        // Fetch status after a short delay to get updated status
        setTimeout(fetchAllCameraStatus, 1000);
      } else {
        setError(`Failed to start camera: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error starting camera:', error);
      setError(`Failed to start camera: ${error.message}`);
    }
  };

  const stopCamera = async (cameraId) => {
    try {
      const response = await fetch('/api/camera/monitor/stop/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          camera_id: cameraId
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success) {
        // Update camera status
        setCameraStatus(prev => ({
          ...prev,
          [cameraId]: {
            ...prev[cameraId],
            status: {
              ...prev[cameraId]?.status,
              status: 'inactive'
            }
          }
        }));
        
        // Fetch status after a short delay to get updated status
        setTimeout(fetchAllCameraStatus, 1000);
      } else {
        setError(`Failed to stop camera: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error stopping camera:', error);
      setError(`Failed to stop camera: ${error.message}`);
    }
  };

  const startAllCameras = async () => {
    try {
      const response = await fetch('/api/camera/monitor/start_all/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          config: config
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success) {
        // Update all camera statuses to connecting
        const newStatus = { ...cameraStatus };
        cameras.forEach(camera => {
          newStatus[camera.id] = {
            ...newStatus[camera.id],
            status: {
              ...newStatus[camera.id]?.status,
              status: 'connecting'
            }
          };
        });
        setCameraStatus(newStatus);
        
        // Fetch status after a short delay to get updated status
        setTimeout(fetchAllCameraStatus, 1000);
      } else {
        setError(`Failed to start all cameras: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error starting all cameras:', error);
      setError(`Failed to start all cameras: ${error.message}`);
    }
  };

  const stopAllCameras = async () => {
    try {
      const response = await fetch('/api/camera/monitor/stop_all/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const data = await response.json();
      if (data.success) {
        // Update all camera statuses to inactive
        const newStatus = { ...cameraStatus };
        cameras.forEach(camera => {
          newStatus[camera.id] = {
            ...newStatus[camera.id],
            status: {
              ...newStatus[camera.id]?.status,
              status: 'inactive'
            }
          };
        });
        setCameraStatus(newStatus);
        
        // Fetch status after a short delay to get updated status
        setTimeout(fetchAllCameraStatus, 1000);
      } else {
        setError(`Failed to stop all cameras: ${data.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error stopping all cameras:', error);
      setError(`Failed to stop all cameras: ${error.message}`);
    }
  };

  const takeSnapshot = async (cameraId) => {
    try {
      const response = await fetch(`/api/camera/monitor/snapshot/${cameraId}/`);
      if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `camera_${cameraId}_snapshot_${new Date().toISOString().replace(/:/g, '-')}.jpg`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error taking snapshot:', error);
      setError(`Failed to take snapshot: ${error.message}`);
    }
  };

  const handleConfigChange = (e) => {
    const { name, value, type, checked } = e.target;
    setConfig({
      ...config,
      [name]: type === 'checkbox' ? checked : value
    });
  };

  const getCameraStatusClass = (cameraId) => {
    const status = cameraStatus[cameraId]?.status?.status;
    if (!status) return 'status-unknown';
    
    return `status-${status}`;
  };

  const formatFps = (fps) => {
    return fps ? fps.toFixed(1) : '0.0';
  };

  const getStatusLabel = (cameraId) => {
    const status = cameraStatus[cameraId]?.status?.status;
    if (!status) return 'Unknown';
    
    switch (status) {
      case 'active': return 'Active';
      case 'inactive': return 'Inactive';
      case 'connecting': return 'Connecting';
      case 'error': return 'Error';
      default: return status.charAt(0).toUpperCase() + status.slice(1);
    }
  };

  // Detect if a URL is likely using H.265 based on channel number
  const detectCodecFromUrl = (url) => {
    if (!url) return 'Unknown';
    
    url = url.toLowerCase();
    // Check for Hikvision cameras
    if (url.includes('hikvision') || url.includes('isapi')) {
      // Channels 401, 402 typically use H.265
      if (url.includes('ch=4') || url.includes('/channels/4')) {
        return 'H.265/HEVC';
      }
      // Channels 101, 102 typically use H.264
      else if (url.includes('ch=1') || url.includes('/channels/1')) {
        return 'H.264';
      }
    }
    
    // Check for explicit codec mentions in URL
    if (url.includes('h265') || url.includes('hevc')) {
      return 'H.265/HEVC';
    } else if (url.includes('h264') || url.includes('avc')) {
      return 'H.264';
    }
    
    return 'Auto-detect';
  };

  return (
    <div className="camera-monitor">
      <div className="camera-monitor-header">
        <h2>Advanced Camera Monitor</h2>
        <p>Monitor and control multiple camera streams with advanced settings and low latency</p>
        
        <div className="global-controls">
          <button className="start-all-btn" onClick={startAllCameras}>Start All Cameras</button>
          <button className="stop-all-btn" onClick={stopAllCameras}>Stop All Cameras</button>
          <button 
            className="settings-btn" 
            onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
          >
            {showAdvancedSettings ? 'Hide Advanced Settings' : 'Show Advanced Settings'}
          </button>
        </div>
        
        {error && (
          <div className="error-message">
            <p>{error}</p>
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}
        
        {showAdvancedSettings && (
          <div className="advanced-settings">
            <h3>Advanced Stream Settings</h3>
            <div className="settings-grid">
              <div className="setting-item">
                <label>
                  <input 
                    type="checkbox" 
                    name="hardware_acceleration" 
                    checked={config.hardware_acceleration} 
                    onChange={handleConfigChange}
                  />
                  Hardware Acceleration
                </label>
                <p className="setting-description">Uses GPU for faster decoding (if available)</p>
              </div>
              
              <div className="setting-item">
                <label>
                  <input 
                    type="checkbox" 
                    name="low_latency" 
                    checked={config.low_latency} 
                    onChange={handleConfigChange}
                  />
                  Low Latency Mode
                </label>
                <p className="setting-description">Reduces delay but may cause more stuttering</p>
              </div>
              
              <div className="setting-item">
                <label>Transport Protocol</label>
                <select 
                  name="transport" 
                  value={config.transport} 
                  onChange={handleConfigChange}
                >
                  <option value="tcp">TCP (more reliable)</option>
                  <option value="udp">UDP (lower latency)</option>
                  <option value="http">HTTP (firewall friendly)</option>
                </select>
              </div>
              
              <div className="setting-item">
                <label>Buffer Size (frames)</label>
                <select 
                  name="buffer_size" 
                  value={config.buffer_size} 
                  onChange={handleConfigChange}
                >
                  <option value="0">0 (lowest latency)</option>
                  <option value="1">1</option>
                  <option value="3">3</option>
                  <option value="5">5 (balanced)</option>
                  <option value="10">10 (smoother)</option>
                  <option value="15">15 (most stable)</option>
                </select>
              </div>
              
              <div className="setting-item">
                <label>Preferred Codec</label>
                <select 
                  name="codec" 
                  value={config.codec} 
                  onChange={handleConfigChange}
                >
                  <option value="auto">Auto-detect</option>
                  <option value="h264">H.264 (more compatible)</option>
                  <option value="h265">H.265/HEVC (better quality)</option>
                </select>
                <p className="setting-description">H.265 requires hardware support for best performance</p>
              </div>
            </div>
          </div>
        )}
      </div>
      
      <div className="camera-monitor-content">
        <div className="camera-list">
          <h3>Available Cameras ({cameras.length})</h3>
          {loading ? (
            <div className="loading-spinner">Loading cameras...</div>
          ) : cameras.length === 0 ? (
            <p>No cameras found. Add cameras in the Camera Management section.</p>
          ) : (
            <ul>
              {cameras.map(camera => (
                <li 
                  key={camera.id} 
                  className={`camera-item ${activeCamera && activeCamera.id === camera.id ? 'active' : ''}`}
                  onClick={() => setActiveCamera(camera)}
                >
                  <div className="camera-item-header">
                    <span className="camera-name">{camera.name}</span>
                    <span className={`camera-status ${getCameraStatusClass(camera.id)}`}>
                      {getStatusLabel(camera.id)}
                    </span>
                  </div>
                  <div className="camera-location">{camera.location_description}</div>
                  <div className="camera-stats">
                    <div className="stat-item">
                      <span className="stat-label">Resolution:</span>
                      <span className="stat-value">{camera.resolution_width}x{camera.resolution_height}</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">Codec:</span>
                      <span className="stat-value">{detectCodecFromUrl(camera.rtsp_url)}</span>
                    </div>
                  </div>
                  <div className="camera-actions">
                    {cameraStatus[camera.id]?.status?.status === 'active' ? (
                      <button 
                        className="stop-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          stopCamera(camera.id);
                        }}
                      >
                        Stop
                      </button>
                    ) : cameraStatus[camera.id]?.status?.status !== 'connecting' && (
                      <button 
                        className="start-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          startCamera(camera.id);
                        }}
                      >
                        Start
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        
        <div className="camera-view">
          {activeCamera ? (
            <>
              <div className="camera-view-header">
                <h3>{activeCamera.name}</h3>
                <div className="camera-view-controls">
                  {cameraStatus[activeCamera.id]?.status?.status === 'active' && (
                    <button 
                      className="control-btn"
                      onClick={() => takeSnapshot(activeCamera.id)}
                      disabled={!cameraStatus[activeCamera.id]?.status?.is_active}
                    >
                      <i className="fas fa-camera"></i>
                    </button>
                  )}
                </div>
              </div>
              
              <div className="camera-stream-container">
                {cameraStatus[activeCamera.id]?.status?.status === 'active' ? (
                  <>
                    <img 
                      ref={imgRef} 
                      className="camera-stream" 
                      alt={`Stream from ${activeCamera.name}`} 
                    />
                    {cameraStatus[activeCamera.id]?.status && (
                      <div className="stream-stats">
                        <div className="stat-item">
                          <span className="stat-label">FPS:</span>
                          <span className="stat-value">{formatFps(cameraStatus[activeCamera.id]?.status?.fps)}</span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Codec:</span>
                          <span className="stat-value">{cameraStatus[activeCamera.id]?.status?.codec || config.codec}</span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">HW:</span>
                          <span className="stat-value">{cameraStatus[activeCamera.id]?.status?.hardware_acceleration || 'none'}</span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Transport:</span>
                          <span className="stat-value">{cameraStatus[activeCamera.id]?.status?.transport}</span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Frames:</span>
                          <span className="stat-value">{cameraStatus[activeCamera.id]?.status?.frames_processed || 0}</span>
                        </div>
                        <div className="stat-item">
                          <span className="stat-label">Dropped:</span>
                          <span className="stat-value">{cameraStatus[activeCamera.id]?.status?.frames_dropped || 0}</span>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="camera-placeholder">
                    <div className="placeholder-content">
                      <span className="placeholder-icon">📹</span>
                      <p>
                        {cameraStatus[activeCamera.id]?.status?.status === 'connecting' 
                          ? 'Connecting to camera...' 
                          : cameraStatus[activeCamera.id]?.status?.status === 'error'
                            ? `Error: ${cameraStatus[activeCamera.id]?.status?.error || 'Unknown error'}`
                            : 'Camera is not active. Click "Start" to begin streaming.'}
                      </p>
                      {cameraStatus[activeCamera.id]?.status?.status !== 'connecting' && (
                        <button 
                          className="start-btn"
                          onClick={() => startCamera(activeCamera.id)}
                        >
                          Start Camera
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
              
              <div className="camera-details">
                <h4>Camera Details</h4>
                <div className="details-grid">
                  <div className="detail-item">
                    <span className="detail-label">Location:</span>
                    <span className="detail-value">{activeCamera.location_description}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Resolution:</span>
                    <span className="detail-value">{activeCamera.resolution_width}x{activeCamera.resolution_height}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Target FPS:</span>
                    <span className="detail-value">{activeCamera.fps}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">Codec:</span>
                    <span className="detail-value">{detectCodecFromUrl(activeCamera.rtsp_url)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="detail-label">RTSP URL:</span>
                    <span className="detail-value rtsp-url">{activeCamera.rtsp_url}</span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="no-camera-selected">
              <p>Select a camera from the list to view its stream</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CameraMonitor;
