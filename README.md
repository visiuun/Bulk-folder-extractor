# Bulk Folder Extractor

This tool is a Python-based GUI utility designed to copy files from one folder to another. Users can choose whether to copy files sequentially (all at once) or concurrently (each file in a separate thread). The tool uses the `tkinter` library for folder selection and provides notifications upon completion.

## Features

- **GUI-based Folder Selection**: Select input and output folders using a graphical file dialog.
- **Two Copy Modes**:
  - **Sequential Copy**: All files are copied one after the other.
  - **Concurrent Copy**: Each file is copied in its own thread, improving performance for large batches.
- **Error Handling**: Ensures proper notifications for missing input/output folders or if copying is incomplete.
- **Progress Logs**: Prints a log of each file copied to the console for tracking.

## Requirements

Ensure the following Python libraries are installed:
- `os` (standard library)
- `shutil` (standard library)
- `pathlib` (standard library)
- `tkinter` (standard library, pre-installed with Python on most systems)
- `threading` (standard library)

## Installation

No installation is required for this script. Ensure Python is installed on your system, and you're ready to run it.

## Usage

1. **Run the Script**:
   Run the script using Python:
   ```bash
   python "bulk folder extractor.py"
   ```

2. **Select Folders**:
   - A dialog will prompt you to select the input folder (source of files).
   - A second dialog will prompt you to select the output folder (destination).

3. **Choose Copy Mode**:
   - When prompted, choose whether to copy files **sequentially** or **concurrently**:
     - Select "Yes" for sequential copying.
     - Select "No" for concurrent copying.

4. **View Progress**:
   - The console will display logs for each file copied.
   - A message box will notify you upon successful completion.

## Example

1. Run the script:
   ```bash
   python "bulk folder extractor.py"
   ```
2. Select an input folder like `/Users/username/Documents/input_files`.
3. Select an output folder like `/Users/username/Documents/output_files`.
4. Choose your preferred copy mode.
5. Wait for the process to complete and review the logs in the terminal or console.

## Customization

To modify the tool:
- **Change the default behavior**: Adjust the `copy_all` parameter in the `copy_folder_contents` function.
- **Add filters**: Customize the `os.walk()` loop to filter files based on extensions or other criteria.

## Known Limitations

- This tool does not display progress bars. For larger directories, real-time feedback is limited to console logs.
- Large numbers of concurrent threads may strain system resources.

## License

This tool is open-source and free to use. Modify it to suit your needs.

--- 
