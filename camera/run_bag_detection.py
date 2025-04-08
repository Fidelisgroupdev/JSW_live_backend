"""
Script to run cement bag detection with line crossing for a specific camera.
"""
import argparse
import os
import sys
import django

# Add the project root directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cement_track.settings')
django.setup()

from camera.cement_bag_detection import process_rtsp_stream
from camera.models import Camera
from inventory.models import Cluster

def main():
    parser = argparse.ArgumentParser(description="Run cement bag detection with line crossing")
    parser.add_argument("--camera_id", type=int, required=True, help="Camera ID in the database")
    parser.add_argument("--output", help="Path to save output video")
    parser.add_argument("--api_url", default="http://127.0.0.1:8000/api/camera/process-bag-detection/",
                       help="API endpoint URL")
    parser.add_argument("--confidence", type=float, default=0.5, help="Detection confidence threshold")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="Device to run inference on")
    parser.add_argument("--no_display", action="store_true", help="Don't display output")
    
    args = parser.parse_args()
    
    try:
        # Get camera from database
        camera = Camera.objects.get(id=args.camera_id)
        print(f"Found camera: {camera.name} at {camera.rtsp_url}")
        
        # Get clusters monitored by this camera
        clusters = camera.coverage_clusters.all()
        print(f"Camera monitors {clusters.count()} clusters")
        
        # Create lines between clusters
        lines = []
        
        # Get camera resolution
        width = camera.resolution_width
        height = camera.resolution_height
        
        if clusters.count() > 1:
            # Sort clusters by position
            sorted_clusters = sorted(clusters, key=lambda c: (c.location_x, c.location_y))
            
            # Create lines between adjacent clusters
            for i in range(len(sorted_clusters) - 1):
                cluster1 = sorted_clusters[i]
                cluster2 = sorted_clusters[i + 1]
                
                # Create a line between these clusters
                # In a real implementation, you would calculate the actual position based on
                # camera calibration and cluster positions in the warehouse
                
                # For now, we'll create evenly spaced horizontal lines
                y_position = int(height * (i + 1) / len(sorted_clusters))
                
                line = {
                    'id': f'line_{cluster1.id}_{cluster2.id}',
                    'start': (0, y_position),
                    'end': (width, y_position),
                    'cluster_from': cluster1.id,
                    'cluster_to': cluster2.id
                }
                
                lines.append(line)
                print(f"Created line between clusters {cluster1.name} and {cluster2.name}")
        else:
            # If only one cluster or no clusters, create a default line
            default_line = {
                'id': 'default_line',
                'start': (0, height // 2),
                'end': (width, height // 2),
                'cluster_from': clusters[0].id if clusters.count() > 0 else None,
                'cluster_to': None
            }
            lines.append(default_line)
            print("Created default line")
        
        # Run detection
        print(f"Starting detection on camera {camera.name} ({camera.rtsp_url})")
        process_rtsp_stream(
            rtsp_url=camera.rtsp_url,
            camera_id=args.camera_id,
            cluster_lines=lines,
            output_path=args.output,
            api_url=args.api_url,
            confidence=args.confidence,
            device=args.device,
            display=not args.no_display
        )
    
    except Camera.DoesNotExist:
        print(f"Error: Camera with ID {args.camera_id} not found")
        return
    
    except Exception as e:
        print(f"Error: {e}")
        return

if __name__ == "__main__":
    main()
