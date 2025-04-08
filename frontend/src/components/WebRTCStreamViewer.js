import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import './WebRTCStreamViewer.css';

const PROXY_SERVER_URL = 'http://localhost:3001';

const WebRTCStreamViewer = ({ rtspUrl, cameraName, autoPlay = true }) => {
  const videoRef = useRef(null);
  const [streamId, setStreamId] = useState('');
  const [status, setStatus] = useState('initializing');
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;
    
    const setupStream = async () => {
      if (!rtspUrl) {
        setStatus('idle');
        return;
      }

      try {
        setStatus('connecting');
        
        // Generate a unique stream ID based on the RTSP URL
        const uniqueId = btoa(rtspUrl).replace(/[+/=]/g, '').substring(0, 16);
        
        // Create the stream on the proxy server
        const response = await axios.post(`${PROXY_SERVER_URL}/api/create-stream`, {
          streamId: uniqueId,
          rtspUrl: rtspUrl
        });
        
        if (isMounted) {
          if (response.data.success) {
            setStreamId(uniqueId);
            setStatus('connected');
            
            // Load the WebRTC player
            const script = document.createElement('script');
            script.src = `${PROXY_SERVER_URL}/rtsp-relay.js`;
            script.async = true;
            script.onload = () => {
              if (isMounted && window.loadPlayer && videoRef.current) {
                window.loadPlayer({
                  videoEl: videoRef.current,
                  pathname: uniqueId,
                  host: PROXY_SERVER_URL.replace('http://', '').replace('https://', ''),
                  secure: PROXY_SERVER_URL.startsWith('https'),
                  onDisconnect: () => {
                    if (isMounted) {
                      setStatus('disconnected');
                      setError('Stream disconnected. The camera may be offline.');
                    }
                  }
                });
              }
            };
            
            document.body.appendChild(script);
          } else {
            setStatus('error');
            setError(response.data.error || 'Failed to create stream');
          }
        }
      } catch (err) {
        console.error('Error setting up WebRTC stream:', err);
        if (isMounted) {
          setStatus('error');
          setError(err.response?.data?.error || err.message || 'Failed to connect to stream');
        }
      }
    };
    
    setupStream();
    
    return () => {
      isMounted = false;
      // Cleanup if needed
    };
  }, [rtspUrl]);

  return (
    <div className="webrtc-stream-viewer">
      <div className="stream-header">
        <h3>{cameraName || 'Camera Stream'}</h3>
        <div className={`status-indicator ${status}`}>
          {status === 'connecting' && 'Connecting...'}
          {status === 'connected' && 'Connected'}
          {status === 'disconnected' && 'Disconnected'}
          {status === 'error' && 'Error'}
          {status === 'idle' && 'Ready'}
        </div>
      </div>
      
      <div className="stream-container">
        {status === 'connecting' && (
          <div className="stream-loading">
            <div className="spinner"></div>
            <p>Connecting to stream...</p>
          </div>
        )}
        
        {error && (
          <div className="stream-error">
            <span className="material-icons">error</span>
            <p>{error}</p>
          </div>
        )}
        
        <video 
          ref={videoRef}
          autoPlay={autoPlay}
          playsInline
          muted
          className={status === 'connected' ? 'active' : ''}
        />
      </div>
      
      <div className="stream-info">
        {streamId && (
          <div className="stream-details">
            <p>Stream ID: {streamId}</p>
            <p>Status: {status}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default WebRTCStreamViewer;
