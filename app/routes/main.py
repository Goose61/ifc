import os
import time
import traceback
import threading
import logging
import re
import json
from flask import (
    Blueprint, flash, redirect, render_template, request, 
    url_for, current_app, send_from_directory, jsonify, session, copy_current_request_context
)
from werkzeug.utils import secure_filename
from app.models.material_takeoff import MaterialTakeoffAnalyzer
from flask import current_app as app
from app import turbo  # Import the turbo instance

bp = Blueprint('main', __name__)

# Global dictionary to track analysis status
analysis_tasks = {}
# Thread dictionary to keep track of running threads
threads = {}
# Dictionary to track update threads
update_threads = {}

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# Function to send status updates to the client using Turbo-Flask
def update_loading_status(filename, app_instance):
    """Update the loading status using Turbo-Flask."""
    with app_instance.app_context():
        while filename in analysis_tasks:
            task = analysis_tasks.get(filename, {})
            status = task.get('status', 'unknown')
            
            # Calculate elapsed time and time estimations
            if task.get('start_time'):
                elapsed_seconds = time.time() - task.get('start_time')
                task['elapsed_time'] = elapsed_seconds
                
                # Format elapsed time
                if elapsed_seconds < 60:
                    task['elapsed_time_formatted'] = f"{int(elapsed_seconds)} seconds"
                elif elapsed_seconds < 3600:
                    minutes = int(elapsed_seconds / 60)
                    seconds = int(elapsed_seconds % 60)
                    task['elapsed_time_formatted'] = f"{minutes} minutes, {seconds} seconds"
                else:
                    hours = int(elapsed_seconds / 3600)
                    minutes = int((elapsed_seconds % 3600) / 60)
                    task['elapsed_time_formatted'] = f"{hours} hours, {minutes} minutes"
                
                # Calculate time estimation
                processed = task.get('processed_elements', 0)
                if task.get('detailed_processing_elements', 0) > 0:
                    processed = task.get('detailed_processing_elements')
                
                total = task.get('total_elements', 0)
                
                if processed > 0 and elapsed_seconds > 0 and total > 0:
                    # Calculate processing rate
                    elements_per_second = processed / elapsed_seconds
                    task['processing_rate'] = elements_per_second
                    task['processing_rate_formatted'] = f"{elements_per_second:.2f} elements/second"
                    
                    # Calculate remaining time
                    remaining_elements = total - processed
                    if elements_per_second > 0:
                        estimated_seconds = remaining_elements / elements_per_second
                        
                        # Format estimated time
                        if estimated_seconds < 60:
                            task['estimated_time_remaining'] = f"{int(estimated_seconds)} seconds"
                        elif estimated_seconds < 3600:
                            task['estimated_time_remaining'] = f"{int(estimated_seconds / 60)} minutes"
                        else:
                            hours = int(estimated_seconds / 3600)
                            minutes = int((estimated_seconds % 3600) / 60)
                            task['estimated_time_remaining'] = f"{hours} hours, {minutes} minutes"
            
            # If analysis completed or failed, stop the updates
            if status in ['completed', 'failed']:
                # One final update
                loading_html = render_template(
                    'loading_status.html',
                    status=status,
                    task=task,
                    filename=filename,
                    time=time  # Pass the time module to the template
                )
                turbo.push(turbo.replace(loading_html, 'loading-status'))
                
                # If completed, redirect to results page
                if status == 'completed':
                    # Instead of using url_for which requires request context,
                    # store the URL to redirect to in the task
                    task['redirect_url'] = f"/analyze/{filename}"
                    loading_html = render_template(
                        'loading_status.html',
                        status=status,
                        task=task,
                        filename=filename,
                        time=time
                    )
                    # Use JavaScript to redirect on the client-side
                    turbo.push(turbo.replace(loading_html, 'loading-status'))
                break
            
            # Render the loading status template with current task info
            loading_html = render_template(
                'loading_status.html',
                status=status,
                task=task,
                filename=filename,
                time=time  # Pass the time module to the template
            )
            
            # Push the update to the client
            turbo.push(turbo.replace(loading_html, 'loading-status'))
            
            # Sleep before the next update
            time.sleep(1)

@bp.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')

@bp.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    try:
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Secure the filename and add timestamp to avoid overwrites
            timestamp = int(time.time())
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            # Ensure the upload directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save the file
            file.save(file_path)
            
            current_app.logger.info(f"File uploaded: {filename}")
            
            # Initialize analysis task status
            analysis_tasks[filename] = {
                'status': 'pending',
                'error': None,
                'results': None
            }
            
            # Redirect to loading page
            return redirect(url_for('main.loading', filename=filename))
        
        else:
            flash('File type not allowed. Please upload an IFC file.')
            return redirect(url_for('main.index'))
    
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {str(e)}\n{traceback.format_exc()}")
        flash(f'An unexpected error occurred during upload: {str(e)}')
        return redirect(url_for('main.index'))

@bp.route('/loading/<filename>')
def loading(filename):
    """Show loading page and start analysis in background."""
    try:
        # Sanitize filename to prevent path traversal
        filename = os.path.basename(filename)
        
        # Check if file exists
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if not os.path.exists(file_path):
            flash('File not found')
            current_app.logger.warning(f"File not found: {filename}")
            return redirect(url_for('main.index'))
        
        # Save the current application context for the background thread
        upload_folder = current_app.config['UPLOAD_FOLDER']
        app_instance = current_app._get_current_object()
        
        # Start analysis in a background thread if not already started
        if analysis_tasks.get(filename, {}).get('status') == 'pending':
            analysis_tasks[filename]['status'] = 'running'
            
            # Clean up any old thread with the same name
            if filename in threads and threads[filename].is_alive():
                current_app.logger.warning(f"Thread for {filename} already exists. Status update only.")
            else:
                # Create and start new thread with the application context
                thread = threading.Thread(
                    target=analyze_file_task, 
                    args=(filename, upload_folder, app_instance),
                    name=f"analysis_{filename}"
                )
                thread.daemon = True
                thread.start()
                threads[filename] = thread
                current_app.logger.info(f"Started analysis thread for {filename}")
        
        # Start the Turbo-Flask update thread if not already running
        if filename not in update_threads or not update_threads[filename].is_alive():
            # Create and start a thread for Turbo-Flask updates
            update_thread = threading.Thread(
                target=update_loading_status,
                args=(filename, app_instance),
                name=f"update_{filename}"
            )
            update_thread.daemon = True
            update_thread.start()
            update_threads[filename] = update_thread
            current_app.logger.info(f"Started Turbo update thread for {filename}")
        
        # Return loading template
        return render_template('loading.html', filename=filename)
    
    except Exception as e:
        current_app.logger.error(f"Error in loading route: {str(e)}\n{traceback.format_exc()}")
        flash(f'An unexpected error occurred: {str(e)}')
        return redirect(url_for('main.index'))

def analyze_file_task(filename, upload_folder, app):
    """Background task to analyze the file."""
    # Create a Flask application context for this thread
    with app.app_context():
        # Set up thread-specific logging safely
        thread_logger = logging.getLogger(f"analysis_thread_{filename}")
        thread_logger.setLevel(logging.INFO)
        
        # Add a console handler to make sure logs appear somewhere if file handler fails
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        thread_logger.addHandler(console_handler)
        
        try:
            # Sanitize filename to prevent path traversal
            filename = os.path.basename(filename)
            
            file_path = os.path.join(upload_folder, filename)
            
            # Initial update to status - set the analysis start time
            analysis_start_time = time.time()
            analysis_tasks[filename] = {
                **analysis_tasks[filename],
                'status': 'running',
                'processed_elements': 0,
                'detailed_processing_elements': 0,  # Initialize detailed processing counter
                'phase': 'initializing',
                'phase_description': 'Loading IFC file',
                'start_time': analysis_start_time
            }
            thread_logger.info(f"Starting analysis for {filename}")
            
            # Create analyzer instance
            analyzer = MaterialTakeoffAnalyzer(file_path)
            
            # Set up log message interceptor to track detailed processing progress
            class DetailedProcessingLogHandler(logging.Handler):
                def emit(self, record):
                    message = record.getMessage()
                    # Look for detailed processing messages of the format: "Processed X/Y elements (Z%)"
                    match = re.search(r"Processed (\d+)/(\d+) elements", message)
                    if match:
                        processed = int(match.group(1))
                        total = int(match.group(2))
                        # Update the task with detailed processing progress
                        if filename in analysis_tasks:
                            analysis_tasks[filename]['detailed_processing_elements'] = processed
            
            # Add the detailed processing tracker log handler
            detailed_log_handler = DetailedProcessingLogHandler()
            analyzer.logger.addHandler(detailed_log_handler)
            
            # Update status to reflect file is loaded
            analysis_tasks[filename]['phase'] = 'analyzing'
            analysis_tasks[filename]['phase_description'] = 'Preparing to analyze elements'
            thread_logger.info(f"Created analyzer for {filename}")
            
            # Get total element count
            total_elements = len(analyzer.ifc_file.by_type('IfcProduct'))
            
            # Update task with element count and phase
            analysis_tasks[filename].update({
                'total_elements': total_elements,
                'phase_description': f'Analyzing {total_elements} elements'
            })
            
            thread_logger.info(f"IFC file contains {total_elements} elements")
            
            # Store the original analyze_all_elements method
            original_analyze_all_elements = analyzer.analyze_all_elements
            
            # Create a proxy method to simulate slower progress updates
            def analyze_all_elements_with_progress():
                # Reset processed elements counter
                analysis_tasks[filename]['processed_elements'] = 0
                analysis_tasks[filename]['total_elements'] = total_elements
                
                # Start element processing timer
                elements_start_time = time.time()
                thread_logger.info(f"Starting detailed analysis of {total_elements} elements")
                
                # Instead of immediately counting all elements, we'll do a separate, faster pass
                # to get accurate element count, and then simulate slower progress during actual analysis
                elements_list = list(analyzer.ifc_file.by_type('IfcProduct'))
                
                # Launch a background thread to update progress while analysis runs
                def update_progress_during_analysis():
                    # Estimate a reasonable analysis time based on element count
                    # Usually analysis takes about 5-10 seconds per 5000 elements
                    estimated_analysis_seconds = max(8, total_elements / 1000)
                    
                    # Calculate how many progress updates to do (1 per 2% progress)
                    update_count = 50  # Update approximately 50 times (2% increments)
                    sleep_time = estimated_analysis_seconds / update_count
                    
                    # Sleep to simulate initialization
                    time.sleep(1)
                    
                    # Update progress at regular intervals
                    for i in range(1, update_count+1):
                        try:
                            # Calculate simulated progress
                            simulated_progress = int((i / update_count) * total_elements)
                            
                            # Update progress in task status
                            analysis_tasks[filename]['processed_elements'] = min(simulated_progress, total_elements)
                            
                            # Log progress
                            if i % 5 == 0:  # Log every 10% progress
                                thread_logger.info(
                                    f"Analysis progress: {simulated_progress}/{total_elements} elements "
                                    f"({(simulated_progress/total_elements)*100:.1f}%)"
                                )
                            
                            # Sleep until next update
                            time.sleep(sleep_time)
                            
                            # Stop if analysis is complete
                            if analysis_tasks[filename].get('analysis_complete'):
                                break
                                
                        except Exception as e:
                            thread_logger.warning(f"Error updating progress: {str(e)}")
                
                # Start progress updater thread
                progress_thread = threading.Thread(
                    target=update_progress_during_analysis,
                    name=f"progress_{filename}"
                )
                progress_thread.daemon = True
                progress_thread.start()
                
                # Call the original method to do the actual analysis
                try:
                    result = original_analyze_all_elements()
                finally:
                    # Mark analysis as complete to stop progress thread
                    analysis_tasks[filename]['analysis_complete'] = True
                    analysis_tasks[filename]['processed_elements'] = total_elements
                
                # Wait for progress thread to finish
                if progress_thread.is_alive():
                    progress_thread.join(timeout=2)
                
                return result
            
            # Replace the method with our progress-tracking version
            analyzer.analyze_all_elements = analyze_all_elements_with_progress
            
            # Analyze all elements
            thread_logger.info(f"Analyzing elements for {filename}")
            analyze_start_time = time.time()
            analyzer.analyze_all_elements()
            analyze_end_time = time.time()
            analyze_duration = analyze_end_time - analyze_start_time
            
            # Calculate and log analysis time
            thread_logger.info(
                f"Finished analyzing {total_elements} elements in {analyze_duration:.1f} seconds "
                f"(avg: {total_elements/analyze_duration:.1f} elements/second)"
            )
            
            # Ensure processed_elements is updated to final count
            analysis_tasks[filename]['processed_elements'] = total_elements
            
            # Update status to next phase
            analysis_tasks[filename].update({
                'phase': 'generating_results',
                'phase_description': 'Generating summary and reports',
                'element_processing_complete': True,
                'element_processing_time': analyze_duration
            })
            
            # Generate summary
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(upload_folder, base_name)
            
            # First save results as JSON (prioritize this format)
            thread_logger.info(f"Saving JSON results for {filename}")
            json_file = f"{base_name}_material_takeoff.json"
            json_path = os.path.join(upload_folder, json_file)
            
            try:
                with open(json_path, 'w') as f:
                    json.dump(analyzer.results, f, indent=4)
                thread_logger.info(f"Saved JSON results to {json_path}")
            except Exception as e:
                thread_logger.error(f"Error saving JSON file: {str(e)}")
                analysis_tasks[filename].update({
                    'status': 'failed',
                    'error': f"Failed to save JSON results: {str(e)}"
                })
                return
            
            # Then generate other formats
            thread_logger.info(f"Saving additional result formats for {filename}")
            try:
                # Save Excel file
                excel_file = f"{base_name}_material_takeoff.xlsx"
                analyzer.save_results(output_format='excel')
                
                # Save CSV summary
                summary_file = f"{base_name}_material_takeoff_summary.csv"
                details_file = f"{base_name}_material_takeoff_details.csv"
                analyzer.save_results(output_format='csv')
                
                thread_logger.info(f"Saved all result files for {filename}")
                
                # Update task status with result file locations
                analysis_tasks[filename].update({
                    'status': 'completed',
                    'phase': 'complete',
                    'phase_description': 'Analysis complete',
                    'total_analysis_time': time.time() - analysis_start_time,
                    'results': {
                        'excel_file': excel_file,
                        'json_file': json_file,
                        'summary_file': summary_file,
                        'details_file': details_file,
                        'output_path': output_path
                    }
                })
                
            except Exception as e:
                thread_logger.error(f"Error saving result files: {str(e)}")
                # Even if other formats fail, we still have the JSON, so mark as completed
                # but with a warning
                analysis_tasks[filename].update({
                    'status': 'completed',
                    'phase': 'complete',
                    'phase_description': 'Analysis complete with warnings',
                    'warning': f"Some export formats could not be generated: {str(e)}",
                    'total_analysis_time': time.time() - analysis_start_time,
                    'results': {
                        'json_file': json_file,
                        'output_path': output_path
                    }
                })
                
        except Exception as e:
            error_message = f"Analysis failed: {str(e)}"
            thread_logger.error(f"{error_message}\n{traceback.format_exc()}")
            
            # Update task status
            analysis_tasks[filename].update({
                'status': 'failed',
                'error': error_message,
                'phase': 'error',
                'phase_description': 'Analysis failed due to an error'
            })
        
        finally:
            # Cleanup thread reference
            if filename in threads:
                del threads[filename]

@bp.route('/analyze/<filename>')
def analyze(filename):
    """View the analysis results for a file."""
    try:
        # Sanitize filename to prevent path traversal
        filename = os.path.basename(filename)
        
        # Check if the analysis task exists
        if filename not in analysis_tasks:
            flash('Analysis task not found. Please try uploading and analyzing the file again.')
            return redirect(url_for('main.index'))
        
        # Get the task status
        task = analysis_tasks[filename]
        status = task.get('status', 'unknown')
        
        if status == 'failed':
            error = task.get('error', 'Unknown error')
            flash(f'Analysis failed: {error}')
            return redirect(url_for('main.index'))
        
        if status == 'running':
            # Redirect to loading page if still running
            return redirect(url_for('main.loading', filename=filename))
        
        if status == 'completed':
            results = task.get('results', {})
            
            # Prioritize JSON file first
            json_file = results.get('json_file', '')
            json_path = os.path.join(current_app.config['UPLOAD_FOLDER'], json_file)
            
            # Check if at least the JSON file exists
            if not os.path.exists(json_path):
                flash('Results file is missing. Please try analyzing the file again.')
                return redirect(url_for('main.index'))
            
            # Get additional result files if they exist
            excel_file = results.get('excel_file', '')
            summary_file = results.get('summary_file', '')
            details_file = results.get('details_file', '')
            
            # Check which additional files exist
            excel_exists = os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], excel_file))
            summary_exists = os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], summary_file))
            details_exists = os.path.exists(os.path.join(current_app.config['UPLOAD_FOLDER'], details_file))
            
            # Read JSON data to display on results page
            try:
                with open(json_path, 'r') as f:
                    json_data = json.load(f)
            except Exception as e:
                current_app.logger.error(f"Error reading JSON file: {str(e)}")
                flash(f'Error reading results file: {str(e)}')
                return redirect(url_for('main.index'))
            
            return render_template(
                'results.html', 
                filename=filename,
                json_file=json_file,
                excel_file=excel_file if excel_exists else None,
                summary_file=summary_file if summary_exists else None,
                details_file=details_file if details_exists else None,
                json_data=json_data,
                has_warning=task.get('warning', None)
            )
        
        # Default case - should not reach here
        flash('Unknown analysis status')
        return redirect(url_for('main.index'))
    
    except Exception as e:
        current_app.logger.error(f"Error in analyze route: {str(e)}\n{traceback.format_exc()}")
        flash(f'An unexpected error occurred: {str(e)}')
        return redirect(url_for('main.index'))

@bp.route('/download/<filename>')
def download_file(filename):
    """Download a file."""
    try:
        # Sanitize filename to prevent path traversal
        filename = os.path.basename(filename)
        
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            flash(f'File not found: {filename}')
            return redirect(url_for('main.index'))
        
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            filename,
            as_attachment=True
        )
    except FileNotFoundError:
        current_app.logger.error(f"Download file not found: {filename}")
        flash(f'File not found: {filename}')
        return redirect(url_for('main.index'))
    except Exception as e:
        current_app.logger.error(f"Error downloading file: {filename} - {str(e)}\n{traceback.format_exc()}")
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('main.index')) 