import os
import shutil
from pathlib import Path
from tkinter import Tk, filedialog, messagebox
import threading

def copy_file(file_path, dest_path):
    """Copy a single file to the destination"""
    shutil.copy2(file_path, dest_path)
    print(f"Copied: {file_path} to {dest_path}")

def copy_folder_contents(input_folder, output_folder, copy_all=False):
    """Copy folder contents, either all files in one go or separate threads per file"""
    files_to_copy = []

    # Collect all files to copy
    for root, _, files in os.walk(input_folder):
        for file in files:
            file_path = Path(root) / file
            dest_path = Path(output_folder) / file
            files_to_copy.append((file_path, dest_path))

    if copy_all:
        # Copy all files in one go (sequentially)
        for file_path, dest_path in files_to_copy:
            shutil.copy2(file_path, dest_path)
            print(f"Copied: {file_path} to {dest_path}")
        messagebox.showinfo("Copy Completed", "All files copied successfully.")
    else:
        # Use threading to copy files concurrently
        threads = []
        for file_path, dest_path in files_to_copy:
            # Create and start a new thread for each file copy operation
            thread = threading.Thread(target=copy_file, args=(file_path, dest_path))
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to finish
        for thread in threads:
            thread.join()

        messagebox.showinfo("Copy Completed", "Files copied concurrently.")

def select_folders():
    """Prompt user to select folders and start the copy process"""
    root = Tk()
    root.withdraw()  # Hide the root window
    
    # Prompt user to select the input folder
    input_folder = filedialog.askdirectory(title="Select the input folder containing files and folders")
    if not input_folder:
        print("No input folder selected. Exiting...")
        messagebox.showinfo("No Input Folder", "No input folder selected. Exiting...")
        return
    
    # Prompt user to select the output folder
    output_folder = filedialog.askdirectory(title="Select the output folder to copy files to")
    if not output_folder:
        print("No output folder selected. Exiting...")
        messagebox.showinfo("No Output Folder", "No output folder selected. Exiting...")
        return

    # Ask user if they want to copy files sequentially or concurrently
    copy_all = messagebox.askyesno(
        title="Select Copy Mode",
        message="Do you want to copy all files at once (sequentially)?"
    )
    
    # Start copying folder contents
    copy_folder_contents(input_folder, output_folder, copy_all)

# Run the folder selection and copy process
if __name__ == "__main__":
    select_folders()
