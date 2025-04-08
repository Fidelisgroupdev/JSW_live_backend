import json
import os
import shutil
from pathlib import Path
import argparse

def convert_bbox_coco_to_yolo(bbox, img_width, img_height):
    """
    Convert bounding box from COCO format [x, y, width, height] to YOLO format
    [x_center, y_center, width, height] where all values are normalized between 0 and 1
    """
    x, y, w, h = bbox
    
    # Calculate center coordinates
    x_center = x + w / 2
    y_center = y + h / 2
    
    # Normalize values
    x_center /= img_width
    y_center /= img_height
    w /= img_width
    h /= img_height
    
    return [x_center, y_center, w, h]

def convert_coco_to_yolo(coco_file, output_dir, images_dir=None, copy_images=False):
    """
    Convert COCO format annotations to YOLO format
    
    Args:
        coco_file (str): Path to COCO JSON file
        output_dir (str): Directory to save YOLO annotations
        images_dir (str, optional): Directory containing images (if different from COCO JSON location)
        copy_images (bool): Whether to copy images to output directory
    """
    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    labels_dir = os.path.join(output_dir, 'labels')
    os.makedirs(labels_dir, exist_ok=True)
    
    if copy_images:
        images_output_dir = os.path.join(output_dir, 'images')
        os.makedirs(images_output_dir, exist_ok=True)
    
    # Load COCO JSON file
    with open(coco_file, 'r') as f:
        coco_data = json.load(f)
    
    # Create a mapping from image_id to image details
    images_map = {img['id']: img for img in coco_data['images']}
    
    # Create a mapping from category_id to category index (YOLO uses 0-indexed class IDs)
    categories_map = {cat['id']: idx for idx, cat in enumerate(coco_data['categories'])}
    
    # Create a YAML file for dataset configuration
    yaml_content = {
        'path': os.path.abspath(output_dir),
        'train': 'images/train',
        'val': 'images/val',
        'nc': len(categories_map),
        'names': [cat['name'] for cat in coco_data['categories']]
    }
    
    with open(os.path.join(output_dir, 'dataset.yaml'), 'w') as f:
        f.write('# YOLOv5 dataset configuration\n')
        f.write(f"path: {yaml_content['path']}\n")
        f.write(f"train: {yaml_content['train']}\n")
        f.write(f"val: {yaml_content['val']}\n")
        f.write(f"nc: {yaml_content['nc']}\n")
        f.write(f"names: {yaml_content['names']}\n")
    
    # Process each annotation
    for annotation in coco_data['annotations']:
        image_id = annotation['image_id']
        category_id = annotation['category_id']
        bbox = annotation['bbox']
        
        # Get image details
        img_info = images_map[image_id]
        img_width, img_height = img_info['width'], img_info['height']
        img_filename = img_info['file_name']
        
        # Convert bbox to YOLO format
        yolo_bbox = convert_bbox_coco_to_yolo(bbox, img_width, img_height)
        
        # Get YOLO class ID (0-indexed)
        yolo_class_id = categories_map[category_id]
        
        # Create YOLO annotation line
        yolo_line = f"{yolo_class_id} {yolo_bbox[0]:.6f} {yolo_bbox[1]:.6f} {yolo_bbox[2]:.6f} {yolo_bbox[3]:.6f}\n"
        
        # Write to label file (same name as image but with .txt extension)
        label_filename = os.path.splitext(img_filename)[0] + '.txt'
        label_path = os.path.join(labels_dir, label_filename)
        
        # Append to existing file or create new one
        with open(label_path, 'a') as f:
            f.write(yolo_line)
        
        # Copy image if requested
        if copy_images and images_dir:
            src_img_path = os.path.join(images_dir, img_filename)
            dst_img_path = os.path.join(images_output_dir, img_filename)
            if os.path.exists(src_img_path) and not os.path.exists(dst_img_path):
                shutil.copy2(src_img_path, dst_img_path)
    
    print(f"Conversion completed. YOLO annotations saved to {labels_dir}")
    if copy_images:
        print(f"Images copied to {images_output_dir}")
    print(f"Dataset configuration saved to {os.path.join(output_dir, 'dataset.yaml')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert COCO format annotations to YOLO format')
    parser.add_argument('--coco_file', type=str, required=True, help='Path to COCO JSON file')
    parser.add_argument('--output_dir', type=str, required=True, help='Directory to save YOLO annotations')
    parser.add_argument('--images_dir', type=str, help='Directory containing images (if different from COCO JSON location)')
    parser.add_argument('--copy_images', action='store_true', help='Copy images to output directory')
    
    args = parser.parse_args()
    
    convert_coco_to_yolo(args.coco_file, args.output_dir, args.images_dir, args.copy_images)
