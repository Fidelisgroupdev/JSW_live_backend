import React, { useState } from 'react';
import HikvisionStreamViewer from './HikvisionStreamViewer';
import './RTSPTester.css';

const RTSPTester = () => {
  const [rtspUrl, setRtspUrl] = useState('');
  const [activeStream, setActiveStream] = useState('');
  const [cameraName, setCameraName] = useState('RTSP Test Stream');
  const [resolution, setResolution] = useState('medium');
  const [targetFps, setTargetFps] = useState(25); // Default FPS
  const [isLoading, setIsLoading] = useState(false);
  const [connectionError, setConnectionError] = useState('');

  // Example URLs
  const exampleUrls = [
    {
      name: 'Hikvision Camera',
      url: 'rtsp://admin:password@192.168.1.64:554/Streaming/Channels/101'
    },
    {
      name: 'Public Test Stream',
      url: 'rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4'
    }
  ];

  const handleStartStream = () => {
    if (rtspUrl) {
      setIsLoading(true);
      setConnectionError('');
      setActiveStream(rtspUrl);
    }
  };

  const handleStopStream = () => {
    setActiveStream('');
    setConnectionError('');
  };

  const handleExampleClick = (url) => {
    setRtspUrl(url);
  };
  
  const handleStreamError = (error) => {
    setConnectionError(error);
    setIsLoading(false);
  };
  
  const handleStreamSuccess = () => {
    setIsLoading(false);
    setConnectionError('');
  };

  return (
    <div className="rtsp-tester">
      <div className="rtsp-tester-header">
        <h2>RTSP Stream Tester</h2>
        <p>Test your RTSP camera streams</p>
      </div>

      <div className="rtsp-form-card">
        <div className="rtsp-form">
          <div className="form-group url-input-group">
            <label htmlFor="rtspUrl">RTSP URL:</label>
            <input
              type="text"
              id="rtspUrl"
              value={rtspUrl}
              onChange={(e) => setRtspUrl(e.target.value)}
              placeholder="rtsp://username:password@ip:port/path"
              className="rtsp-url-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="cameraName">Camera Name:</label>
            <input
              type="text"
              id="cameraName"
              value={cameraName}
              onChange={(e) => setCameraName(e.target.value)}
              placeholder="Enter camera name"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Resolution:</label>
              <div className="button-group">
                <button
                  className={resolution === 'low' ? 'active' : ''}
                  onClick={() => setResolution('low')}
                >
                  Low
                </button>
                <button
                  className={resolution === 'medium' ? 'active' : ''}
                  onClick={() => setResolution('medium')}
                >
                  Medium
                </button>
                <button
                  className={resolution === 'high' ? 'active' : ''}
                  onClick={() => setResolution('high')}
                >
                  High
                </button>
              </div>
            </div>

            <div className="form-group">
              <label>Target FPS:</label>
              <div className="button-group">
                <button
                  className={targetFps === 5 ? 'active' : ''}
                  onClick={() => setTargetFps(5)}
                >
                  5 FPS
                </button>
                <button
                  className={targetFps === 10 ? 'active' : ''}
                  onClick={() => setTargetFps(10)}
                >
                  10 FPS
                </button>
                <button
                  className={targetFps === 15 ? 'active' : ''}
                  onClick={() => setTargetFps(15)}
                >
                  15 FPS
                </button>
                <button
                  className={targetFps === 20 ? 'active' : ''}
                  onClick={() => setTargetFps(20)}
                >
                  20 FPS
                </button>
                <button
                  className={targetFps === 25 ? 'active' : ''}
                  onClick={() => setTargetFps(25)}
                >
                  25 FPS
                </button>
                <button
                  className={targetFps === 30 ? 'active' : ''}
                  onClick={() => setTargetFps(30)}
                >
                  30 FPS
                </button>
              </div>
            </div>
          </div>

          <div className="stream-controls">
            <button 
              className="start-stream-btn"
              onClick={handleStartStream}
              disabled={!rtspUrl || isLoading}
            >
              {isLoading ? 'Connecting...' : 'Start Stream'}
            </button>
            <button 
              className="stop-stream-btn"
              onClick={handleStopStream}
              disabled={!activeStream}
            >
              Stop Stream
            </button>
          </div>
        </div>

        <div className="example-urls">
          <h4>Example URLs:</h4>
          <div className="example-buttons">
            {exampleUrls.map((example, index) => (
              <button
                key={index}
                onClick={() => handleExampleClick(example.url)}
                className="example-url-btn"
              >
                {example.name}
              </button>
            ))}
          </div>
        </div>
        
        {connectionError && (
          <div className="connection-error">
            <h4>Connection Error:</h4>
            <p>{connectionError}</p>
            <div className="connection-tips">
              <p>Connection tips:</p>
              <ul>
                <li>Verify the RTSP URL format</li>
                <li>Check username and password</li>
                <li>Ensure the camera is reachable on the network</li>
                <li>Try adding "?rtsp_transport=tcp" to the end of your URL</li>
              </ul>
            </div>
          </div>
        )}
      </div>

      {activeStream && (
        <div className="stream-viewer-container">
          <HikvisionStreamViewer 
            rtspUrl={activeStream} 
            cameraName={cameraName} 
            resolution={resolution}
            targetFps={targetFps}
            onError={handleStreamError}
            onSuccess={handleStreamSuccess}
          />
        </div>
      )}
    </div>
  );
};

export default RTSPTester;
