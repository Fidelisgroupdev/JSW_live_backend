import os
import argparse
import subprocess
from pathlib import Path

def prepare_yolo_dataset(coco_json_path, images_dir, output_dir, val_split=0.2):
    """
    Prepare a YOLO dataset from COCO format annotations
    
    Args:
        coco_json_path (str): Path to COCO JSON file
        images_dir (str): Directory containing images
        output_dir (str): Directory to create YOLO dataset
        val_split (float): Fraction of data to use for validation (0.0-1.0)
    """
    # Create intermediate directory for conversion
    temp_dir = os.path.join(output_dir, 'temp_conversion')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Step 1: Convert COCO to YOLO format
    print("Step 1: Converting COCO annotations to YOLO format...")
    subprocess.run([
        'python', 'coco_to_yolo.py',
        '--coco_file', coco_json_path,
        '--output_dir', temp_dir,
        '--images_dir', images_dir,
        '--copy_images'
    ], check=True)
    
    # Step 2: Set up YOLO dataset structure
    print("\nStep 2: Setting up YOLO dataset structure...")
    subprocess.run([
        'python', 'setup_yolo_dataset.py',
        '--data_dir', temp_dir,
        '--output_dir', output_dir,
        '--val_split', str(val_split)
    ], check=True)
    
    print(f"\nYOLO dataset preparation completed!")
    print(f"Dataset is ready at: {output_dir}")
    print(f"You can use the dataset.yaml file at {os.path.join(output_dir, 'dataset.yaml')} for training")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Prepare YOLO dataset from COCO format annotations')
    parser.add_argument('--coco_json', type=str, required=True, help='Path to COCO JSON file')
    parser.add_argument('--images_dir', type=str, required=True, help='Directory containing images')
    parser.add_argument('--output_dir', type=str, required=True, help='Directory to create YOLO dataset')
    parser.add_argument('--val_split', type=float, default=0.2, help='Fraction of data to use for validation (0.0-1.0)')
    
    args = parser.parse_args()
    
    prepare_yolo_dataset(args.coco_json, args.images_dir, args.output_dir, args.val_split)
