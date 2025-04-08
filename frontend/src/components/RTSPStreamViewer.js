import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

/**
 * Component for viewing RTSP streams in the browser.
 * Uses a polling approach to fetch snapshots from the backend proxy.
 */
const RTSPStreamViewer = ({ 
  cameraId,
  cameraName,
  rtspUrl,
  isActive = true,
  refreshRate = 1000, // Refresh rate in milliseconds
  onError = () => {}
}) => {
  const [streamImage, setStreamImage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [streamActive, setStreamActive] = useState(false);
  const timerRef = useRef(null);
  const mountedRef = useRef(true);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  // Start or stop streaming based on isActive prop
  useEffect(() => {
    if (isActive) {
      startStreaming();
    } else {
      stopStreaming();
    }
    
    return () => stopStreaming();
  }, [isActive, cameraId, rtspUrl, refreshRate]);

  const startStreaming = () => {
    // Clear any existing timer
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    
    // Check stream status first
    checkStreamStatus();
  };

  const checkStreamStatus = async () => {
    try {
      const response = await axios.get(`/api/cameras/${cameraId}/stream_status/`);
      
      if (response.data.is_active) {
        setStreamActive(true);
        fetchSnapshot();
      } else {
        setStreamActive(false);
        setError('Stream is not active');
        setLoading(false);
        
        // Retry after a longer interval
        if (mountedRef.current && isActive) {
          timerRef.current = setTimeout(checkStreamStatus, 5000);
        }
      }
    } catch (err) {
      console.error('Error checking stream status:', err);
      setStreamActive(false);
      setError('Error connecting to stream');
      setLoading(false);
      
      // Retry after a longer interval
      if (mountedRef.current && isActive) {
        timerRef.current = setTimeout(checkStreamStatus, 5000);
      }
    }
  };

  const fetchSnapshot = async () => {
    if (!mountedRef.current || !isActive) return;
    
    setLoading(true);
    
    try {
      const response = await axios.get(`/api/cameras/${cameraId}/stream_snapshot/`);
      
      if (mountedRef.current) {
        if (response.data.snapshot) {
          setStreamImage(response.data.snapshot);
          setError(null);
        } else {
          setError('No image data received');
        }
        setLoading(false);
        
        // Schedule next snapshot fetch
        timerRef.current = setTimeout(fetchSnapshot, refreshRate);
      }
    } catch (err) {
      console.error('Error fetching snapshot:', err);
      
      if (mountedRef.current) {
        setError('Error fetching snapshot');
        setLoading(false);
        
        // Check stream status again after error
        timerRef.current = setTimeout(checkStreamStatus, 3000);
      }
    }
  };

  const stopStreaming = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  // Handle errors
  useEffect(() => {
    if (error) {
      onError(error);
    }
  }, [error, onError]);

  return (
    <div className="rtsp-stream-viewer">
      {loading && !streamImage && (
        <div className="stream-loading">
          <div className="spinner"></div>
          <p>Connecting to stream...</p>
        </div>
      )}
      
      {error && !streamImage && (
        <div className="stream-error">
          <span className="material-icons">error</span>
          <p>{error}</p>
          <p className="stream-url">{rtspUrl}</p>
        </div>
      )}
      
      {streamImage && (
        <div className="stream-container">
          <img 
            src={`data:image/jpeg;base64,${streamImage}`} 
            alt={`${cameraName} stream`}
            className="stream-image"
          />
          <div className="stream-overlay">
            <div className="stream-info">
              <span className="camera-name">{cameraName}</span>
              <span className="stream-status">Live</span>
            </div>
          </div>
        </div>
      )}
      
      {!streamImage && !loading && !error && (
        <div className="stream-placeholder">
          <span className="material-icons">videocam_off</span>
          <p>Stream not available</p>
        </div>
      )}
    </div>
  );
};

export default RTSPStreamViewer;
