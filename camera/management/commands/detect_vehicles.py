"""
Management command to run vehicle detection on RTSP camera streams.
"""
from django.core.management.base import BaseCommand, CommandError
from camera.models import Camera
from camera.vehicle_detection import process_rtsp_stream
import argparse
import torch


class Command(BaseCommand):
    help = 'Run vehicle detection and counting on RTSP camera streams'

    def add_arguments(self, parser):
        parser.add_argument('--camera_id', type=int, help='Camera ID to process (if not provided, will list available cameras)')
        parser.add_argument('--rtsp_url', help='Override RTSP URL (optional)')
        parser.add_argument('--output', help='Path to save output video (optional)')
        parser.add_argument('--confidence', type=float, default=0.5, help='Detection confidence threshold')
        parser.add_argument('--no_display', action='store_true', help="Don't display output")
        parser.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu', 
                           help='Device to run inference on (cpu or cuda)')

    def handle(self, *args, **options):
        camera_id = options.get('camera_id')
        
        # If no camera ID provided, list available cameras
        if camera_id is None:
            cameras = Camera.objects.filter(status='active')
            if not cameras:
                self.stdout.write(self.style.WARNING('No active cameras found.'))
                return
            
            self.stdout.write(self.style.SUCCESS('Available cameras:'))
            for camera in cameras:
                self.stdout.write(f"ID: {camera.id}, Name: {camera.name}, Location: {camera.location_description}")
            
            self.stdout.write(self.style.SUCCESS('\nRun command with --camera_id <ID> to process a specific camera.'))
            return
        
        # Get camera
        try:
            camera = Camera.objects.get(pk=camera_id)
        except Camera.DoesNotExist:
            raise CommandError(f'Camera with ID {camera_id} does not exist')
        
        # Get RTSP URL
        rtsp_url = options.get('rtsp_url') or camera.rtsp_url
        if not rtsp_url:
            raise CommandError(f'No RTSP URL available for camera {camera.name}')
        
        self.stdout.write(self.style.SUCCESS(f'Starting vehicle detection for camera: {camera.name}'))
        self.stdout.write(f'RTSP URL: {rtsp_url}')
        self.stdout.write(f'Device: {options["device"]}')
        
        # Run detection
        try:
            process_rtsp_stream(
                rtsp_url=rtsp_url,
                camera_id=camera.id,
                output_path=options.get('output'),
                api_url='http://127.0.0.1:8000/api/camera/process-vehicle-detection/',
                confidence=options.get('confidence', 0.5),
                device=options.get('device', 'cpu'),
                display=not options.get('no_display', False)
            )
            self.stdout.write(self.style.SUCCESS('Vehicle detection completed'))
        except Exception as e:
            raise CommandError(f'Error processing video stream: {str(e)}')
