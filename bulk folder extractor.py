# -*- coding: utf-8 -*-
"""
Folder Content Copying Utility
... (rest of docstring) ...
Addresses potential race conditions when using flatten + concurrency.
"""

import os
import shutil
import sys
import logging
import time
import threading # Import threading for the lock
from pathlib import Path
from tkinter import Tk, filedialog, messagebox
from typing import List, Tuple, Set, Dict # Added Set, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
MAX_WORKERS = os.cpu_count() or 4

# --- Logging Setup ---
# (Logging setup remains the same)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
        # logging.FileHandler("copy.log")
    ]
)
log = logging.getLogger(__name__)


# --- Helper Functions ---

def find_unique_path_for_flattening(
    target_path: Path, assigned_filenames_in_run: Set[str]
) -> Path:
    """
    Finds a unique path for flattening. Checks both filesystem existence AND
    filenames already assigned during this copy operation preparation phase.
    Adds the final chosen filename to the `assigned_filenames_in_run` set.

    Args:
        target_path: The initial desired destination path (e.g., dest_folder / source_name).
        assigned_filenames_in_run: A set of filenames (like 'file.txt', 'file (1).txt')
                                   already assigned during this copy run's preparation.

    Returns:
        A unique Path object. The name of this path is added to the input set.
    """
    final_path = target_path
    counter = 1
    base_stem = target_path.stem
    suffix = target_path.suffix

    # Check if the initial target name is already taken (on disk or in this run)
    while final_path.exists() or final_path.name in assigned_filenames_in_run:
        new_stem = f"{base_stem} ({counter})"
        final_path = target_path.with_stem(new_stem) # More reliable than manual concatenation
        counter += 1
        if counter > 9999: # Safety break
            log.error(f"Could not find a unique name for {target_path.name} after 9999 attempts within the destination.")
            # Raise an error or return original? Raising is safer to signal failure.
            raise FileExistsError(f"Cannot find unique name for {target_path.name} in {target_path.parent}")

    # Add the chosen unique filename to the set *before* returning
    assigned_filenames_in_run.add(final_path.name)
    if final_path != target_path:
         log.debug(f"Collision detected or name already assigned for '{target_path.name}'. Using '{final_path.name}'.")
    return final_path


# --- Core Copy Logic ---

# (copy_single_file_task remains the same - it receives the *final* destination path)
def copy_single_file_task(source_file: Path, destination_file: Path) -> Tuple[Path, Path, bool, str]:
    """
    Copies a single file, creating destination directories if needed.
    Note: Destination uniqueness must be handled *before* calling this.
    ... (rest of function is identical) ...
    """
    try:
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination_file)
        log.debug(f"Copied: '{source_file}' -> '{destination_file}'")
        return (source_file, destination_file, True, "")
    except OSError as e:
        # Check specifically for the error we are trying to avoid, although it shouldn't happen now
        if isinstance(e, PermissionError) or (hasattr(e, 'winerror') and e.winerror == 32):
             log.error(f"LOCKING/PERMISSION Error copying '{source_file}' to '{destination_file}': {e} - THIS SHOULD NOT HAPPEN WITH THE NEW LOGIC.")
        else:
             log.error(f"OS Error copying '{source_file}' to '{destination_file}': {e}")
        return (source_file, destination_file, False, str(e))
    except Exception as e:
        error_msg = f"Unexpected Error copying '{source_file}' to '{destination_file}': {e}"
        log.error(error_msg, exc_info=True)
        return (source_file, destination_file, False, str(e))


# (discover_files_to_copy remains the same)
def discover_files_to_copy(source_folder: Path) -> List[Path]:
    """
    Recursively finds all files within the source folder.
    ... (function is identical) ...
    """
    files_to_copy = []
    log.info(f"Scanning source folder '{source_folder}' for files...")
    try:
        for item in source_folder.rglob('*'): # Recursive glob
            if item.is_file():
                files_to_copy.append(item)
    except Exception as e:
        log.error(f"Error scanning source folder '{source_folder}': {e}", exc_info=True)
        return [] # Return empty list on scanning error
    log.info(f"Found {len(files_to_copy)} file(s) to copy.")
    return files_to_copy


def run_copy_operations(
    source_folder: Path,
    destination_folder: Path,
    files_to_process: List[Path],
    use_concurrency: bool,
    flatten_structure: bool
) -> Tuple[int, int, int]:
    """
    Manages the copying process, handling structure preservation or flattening.
    Includes synchronized destination path allocation when flattening to prevent race conditions.
    ... (rest of docstring) ...
    """
    success_count = 0
    failure_count = 0
    rename_count = 0
    total_files = len(files_to_process)
    start_time = time.monotonic()

    copy_tasks: List[Tuple[Path, Path]] = []
    preparation_errors = 0

    # --- Prepare Tasks (Calculate Destination Paths - Synchronized if Flattening) ---
    log.info(f"Preparing {total_files} copy tasks...")
    if flatten_structure:
        log.info("Flattening enabled: Calculating unique destination names sequentially before concurrent copy.")
        assigned_filenames_in_run: Set[str] = set() # Track names assigned in this run
        # We don't technically need a lock here if this prep loop itself is sequential,
        # but it doesn't hurt and emphasizes the critical section.
        # preparation_lock = threading.Lock()
    else:
        log.info("Flattening disabled: Preserving source directory structure.")

    for source_file in files_to_process:
        try:
            if flatten_structure:
                # --- Critical Section for Naming ---
                # with preparation_lock: # Lock is optional if this loop is sequential
                target_destination_file = destination_folder / source_file.name
                # Find unique name considering disk AND already assigned names in this run
                final_destination_file = find_unique_path_for_flattening(
                    target_destination_file, assigned_filenames_in_run
                )
                if final_destination_file.name != source_file.name:
                    # Increment rename count ONLY if the final name is different from the ORIGINAL source name
                    # (find_unique_path_for_flattening handles the '(n)' logic)
                    if final_destination_file.stem != source_file.stem or final_destination_file.suffix != source_file.suffix:
                         # A more robust check might compare stems excluding the potential " (n)" suffix
                         # This simple check works if source names don't already contain " (n)"
                         rename_count += 1
                # --- End Critical Section ---
            else:
                # Preserve Structure: Calculate relative path
                relative_path = source_file.relative_to(source_folder)
                final_destination_file = destination_folder / relative_path
                # Ensure parent directory exists for the task (will be checked again in task, but good practice)
                # final_destination_file.parent.mkdir(parents=True, exist_ok=True) # Can do this here or in task

            copy_tasks.append((source_file, final_destination_file))

        except ValueError as e:
             log.error(f"Skipping - Error determining relative path for '{source_file}' within '{source_folder}' (needed for preserve structure): {e}")
             preparation_errors += 1
        except FileExistsError as e: # Catch error from find_unique_path_for_flattening
             log.error(f"Skipping - {e}")
             preparation_errors += 1
        except Exception as e:
             log.error(f"Skipping - Error preparing copy task for '{source_file}': {e}", exc_info=True)
             preparation_errors += 1

    # Update failure count based on preparation errors
    failure_count += preparation_errors
    actual_tasks_count = len(copy_tasks) # Number of tasks successfully prepared

    log.info(f"Successfully prepared {actual_tasks_count} tasks ({preparation_errors} failures during preparation).")
    if rename_count > 0:
         log.info(f"{rename_count} file(s) will be renamed due to name collisions in the destination (flattening).")

    if actual_tasks_count == 0:
        log.warning("No copy tasks were successfully prepared. Aborting copy execution phase.")
        end_time = time.monotonic()
        duration = end_time - start_time
        log.info(f"Copy process finished in {duration:.2f} seconds (aborted).")
        return success_count, failure_count, rename_count # Return current counts


    log.info(f"Starting copy execution for {actual_tasks_count} tasks...")

    # --- Execute Tasks (Concurrent or Sequential) ---
    if use_concurrency and actual_tasks_count > 1: # Only use thread pool if beneficial
        log.info(f"Using concurrent copy mode with up to {MAX_WORKERS} workers.")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix='Copier') as executor:
            future_to_source = {
                executor.submit(copy_single_file_task, src, dest): src
                for src, dest in copy_tasks # Use the pre-calculated final destinations
            }

            processed_count = 0
            for future in as_completed(future_to_source):
                processed_count += 1
                source_file_processed = future_to_source[future]
                try:
                    _, _, success, _ = future.result()
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                    # Log progress using the source file name
                    log.info(f"Progress: {processed_count}/{actual_tasks_count} ({source_file_processed.name}) - {'OK' if success else 'FAIL'}")

                except Exception as exc:
                    failure_count += 1
                    log.exception(f"Progress: {processed_count}/{actual_tasks_count} - Unexpected error getting result for '{source_file_processed}': {exc}")
    else:
        # Use sequential mode if only one task, or if concurrency disabled
        log.info("Using sequential copy mode.")
        for i, (source_file, destination_file) in enumerate(copy_tasks, 1):
            # Log progress using the source file name
            log.info(f"Progress: {i}/{actual_tasks_count} - Copying '{source_file.name}'...")
            _, _, success, _ = copy_single_file_task(source_file, destination_file)
            if success:
                success_count += 1
            else:
                failure_count += 1

    # --- Final Summary ---
    end_time = time.monotonic()
    duration = end_time - start_time
    log.info(f"Copy execution finished in {duration:.2f} seconds.")
    # Final counts include preparation failures
    log.info(f"Overall Result: {success_count} succeeded, {failure_count} failed. {rename_count} file(s) renamed (if flattened).")

    return success_count, failure_count, rename_count


# --- User Interface ---
# (select_folders_and_copy function remains the same as the previous version)
# It correctly gathers user choices for source, dest, flatten, and concurrency
# and passes them to run_copy_operations. The summary message logic also remains valid.
def select_folders_and_copy():
    """Handles user interaction for selecting folders, options, and starts the process."""
    root = Tk()
    root.withdraw()

    # 1. Select Source Folder
    log.info("Prompting for source folder...")
    source_folder_str = filedialog.askdirectory(title="Select SOURCE Folder (Content will be copied)")
    if not source_folder_str:
        log.info("Source folder selection cancelled.")
        messagebox.showinfo("Cancelled", "No source folder selected.")
        return
    source_folder = Path(source_folder_str).resolve()
    log.info(f"Source folder selected: '{source_folder}'")

    # 2. Select Destination Folder
    log.info("Prompting for destination folder...")
    destination_folder_str = filedialog.askdirectory(title="Select DESTINATION Folder")
    if not destination_folder_str:
        log.info("Destination folder selection cancelled.")
        messagebox.showinfo("Cancelled", "No destination folder selected.")
        return
    destination_folder = Path(destination_folder_str).resolve()
    log.info(f"Destination folder selected: '{destination_folder}'")

    # 3. Validate Folders
    if source_folder == destination_folder:
        log.error("Source and destination folders cannot be the same.")
        messagebox.showerror("Invalid Selection", "Source and destination folders cannot be the same.")
        return
    try:
        # Check if destination is *inside* source
        if destination_folder.is_relative_to(source_folder):
             log.error("Destination folder cannot be inside the source folder.")
             messagebox.showerror("Invalid Selection", "Destination folder cannot be inside the source folder.")
             return
    except AttributeError: # is_relative_to added in Python 3.9
        if str(destination_folder).startswith(str(source_folder) + os.sep):
             log.error("Destination folder cannot be inside the source folder.")
             messagebox.showerror("Invalid Selection", "Destination folder cannot be inside the source folder.")
             return

    # 4. Choose Flatten Option
    log.info("Asking user about flattening structure.")
    flatten_structure = messagebox.askyesno(
        title="Flatten Directory Structure?",
        message="Copy all files directly into the destination folder root?\n\n"
                "• Yes (Flatten): All files go into one folder. Duplicates renamed (e.g., file (1).txt).\n"
                "• No (Preserve): Recreate source folder structure in destination.",
        detail="Choose 'No' to keep the original subfolder organization."
    )
    if flatten_structure is None:
        log.info("Flatten option selection cancelled.")
        messagebox.showinfo("Cancelled", "Operation cancelled by user.")
        return

    # 5. Choose Copy Mode (Concurrent/Sequential)
    log.info("Asking user for copy mode.")
    use_concurrency = messagebox.askyesno(
        title="Select Copy Mode",
        message="Use concurrent copying (multiple threads)?\n\n"
                "• Yes (Recommended): Potentially faster.\n"
                "• No: Copies files one by one.",
        detail=f"Concurrent mode uses up to {MAX_WORKERS} threads."
    )
    if use_concurrency is None:
        log.info("Copy mode selection cancelled.")
        messagebox.showinfo("Cancelled", "Operation cancelled by user.")
        return

    # 6. Discover Files
    files_to_copy = discover_files_to_copy(source_folder)
    if not files_to_copy:
        if os.path.exists(source_folder):
             log.info("No files found in the source folder. Nothing to copy.")
             messagebox.showinfo("Empty Source", "No files were found in the selected source folder.")
        else:
             log.error(f"Source folder '{source_folder}' not found or inaccessible during file discovery.")
             messagebox.showerror("Source Error", f"Could not access or find files in the source folder:\n{source_folder}")
        return

    # 7. Execute Copying
    total_files = len(files_to_copy)
    mode_string = "concurrently" if use_concurrency else "sequentially"
    structure_string = "flattening structure" if flatten_structure else "preserving structure"
    log.info(f"Starting copy operation for {total_files} file(s) from '{source_folder}' to '{destination_folder}' ({mode_string}, {structure_string})...")

    success_count, failure_count, rename_count = run_copy_operations(
        source_folder, destination_folder, files_to_copy, use_concurrency, flatten_structure
    )

    # 8. Show Summary Report
    summary_title = "Copy Complete"
    structure_desc = "Flattened structure" if flatten_structure else "Preserved structure"
    summary_message = (
        f"Finished copying from '{source_folder.name}' to '{destination_folder.name}'.\n"
        f"({structure_desc})\n\n"
        f"Files discovered: {total_files}\n" # Total found initially
        f"Successfully copied: {success_count}\n"
        f"Failed/Skipped: {failure_count}" # Includes prep failures + copy failures
    )
    if flatten_structure and rename_count > 0:
        summary_message += f"\nFiles renamed due to collision: {rename_count}"

    if failure_count > 0:
        summary_title = "Copy Complete with Errors/Skips"
        summary_message += "\n\nPlease check the console or log file for details on errors."
        messagebox.showwarning(summary_title, summary_message)
    else:
        messagebox.showinfo(summary_title, summary_message)

    log.info("Script finished.")


# --- Main Execution ---
# (Main execution block remains the same)
if __name__ == "__main__":
    log.info("Copy script started.")
    root = None
    try:
        root = Tk()
        root.withdraw()
        select_folders_and_copy()
    except Exception as e:
        log.critical("An unexpected critical error occurred in the main process.", exc_info=True)
        try:
             messagebox.showerror("Critical Error", f"An unexpected error occurred: {e}\nCheck logs for details.")
        except Exception:
             print(f"CRITICAL ERROR: {e}", file=sys.stderr)
    finally:
        if root:
            try:
                root.destroy()
            except Exception:
                pass
        log.info("Copy script finished.")
