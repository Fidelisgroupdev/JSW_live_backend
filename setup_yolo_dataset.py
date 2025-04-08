import os
import shutil
import random
import argparse
from pathlib import Path

def setup_yolo_dataset(data_dir, output_dir, val_split=0.2):
    """
    Set up a YOLO dataset directory structure and split data into train/val sets
    
    Args:
        data_dir (str): Directory containing YOLO format labels and images
        output_dir (str): Directory to create YOLO dataset structure
        val_split (float): Fraction of data to use for validation (0.0-1.0)
    """
    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    
    # Create train and val directories for images and labels
    train_img_dir = os.path.join(output_dir, 'images', 'train')
    val_img_dir = os.path.join(output_dir, 'images', 'val')
    train_label_dir = os.path.join(output_dir, 'labels', 'train')
    val_label_dir = os.path.join(output_dir, 'labels', 'val')
    
    for directory in [train_img_dir, val_img_dir, train_label_dir, val_label_dir]:
        os.makedirs(directory, exist_ok=True)
    
    # Get all label files
    labels_dir = os.path.join(data_dir, 'labels')
    label_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
    
    # Shuffle and split
    random.shuffle(label_files)
    val_size = int(len(label_files) * val_split)
    train_files = label_files[val_size:]
    val_files = label_files[:val_size]
    
    print(f"Total files: {len(label_files)}")
    print(f"Training set: {len(train_files)} files")
    print(f"Validation set: {len(val_files)} files")
    
    # Copy files to train/val directories
    images_dir = os.path.join(data_dir, 'images')
    
    # Process training files
    for label_file in train_files:
        # Copy label
        src_label = os.path.join(labels_dir, label_file)
        dst_label = os.path.join(train_label_dir, label_file)
        shutil.copy2(src_label, dst_label)
        
        # Copy corresponding image
        image_name = os.path.splitext(label_file)[0] + '.jpg'  # Assuming JPG format
        src_image = os.path.join(images_dir, image_name)
        
        # Try other extensions if JPG doesn't exist
        if not os.path.exists(src_image):
            for ext in ['.JPG', '.png', '.PNG', '.jpeg', '.JPEG']:
                alt_image_name = os.path.splitext(label_file)[0] + ext
                alt_src_image = os.path.join(images_dir, alt_image_name)
                if os.path.exists(alt_src_image):
                    src_image = alt_src_image
                    image_name = alt_image_name
                    break
        
        if os.path.exists(src_image):
            dst_image = os.path.join(train_img_dir, image_name)
            shutil.copy2(src_image, dst_image)
        else:
            print(f"Warning: Image for {label_file} not found")
    
    # Process validation files
    for label_file in val_files:
        # Copy label
        src_label = os.path.join(labels_dir, label_file)
        dst_label = os.path.join(val_label_dir, label_file)
        shutil.copy2(src_label, dst_label)
        
        # Copy corresponding image
        image_name = os.path.splitext(label_file)[0] + '.jpg'  # Assuming JPG format
        src_image = os.path.join(images_dir, image_name)
        
        # Try other extensions if JPG doesn't exist
        if not os.path.exists(src_image):
            for ext in ['.JPG', '.png', '.PNG', '.jpeg', '.JPEG']:
                alt_image_name = os.path.splitext(label_file)[0] + ext
                alt_src_image = os.path.join(images_dir, alt_image_name)
                if os.path.exists(alt_src_image):
                    src_image = alt_src_image
                    image_name = alt_image_name
                    break
        
        if os.path.exists(src_image):
            dst_image = os.path.join(val_img_dir, image_name)
            shutil.copy2(src_image, dst_image)
        else:
            print(f"Warning: Image for {label_file} not found")
    
    # Create dataset.yaml file
    yaml_path = os.path.join(output_dir, 'dataset.yaml')
    
    # Find class names from an existing label file
    class_names = []
    if label_files:
        # Try to determine class names from the project structure
        # This is a simple approach - in a real project you might want to specify class names manually
        class_names = ["cement_bag"]  # Default class name
    
    with open(yaml_path, 'w') as f:
        f.write('# YOLOv5 dataset configuration\n')
        f.write(f"path: {os.path.abspath(output_dir)}\n")
        f.write(f"train: images/train\n")
        f.write(f"val: images/val\n")
        f.write(f"nc: {len(class_names)}\n")
        f.write(f"names: {class_names}\n")
    
    print(f"Dataset setup completed at {output_dir}")
    print(f"Dataset configuration saved to {yaml_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Set up YOLO dataset structure')
    parser.add_argument('--data_dir', type=str, required=True, help='Directory containing YOLO format labels and images')
    parser.add_argument('--output_dir', type=str, required=True, help='Directory to create YOLO dataset structure')
    parser.add_argument('--val_split', type=float, default=0.2, help='Fraction of data to use for validation (0.0-1.0)')
    
    args = parser.parse_args()
    
    setup_yolo_dataset(args.data_dir, args.output_dir, args.val_split)
