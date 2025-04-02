import os
import logging
from logging.handlers import RotatingFileHandler
from app import create_app

# Create the Flask application
app = create_app()

# Configure logging
if not os.path.exists('logs'):
    os.mkdir('logs')

# Try to set up logging with exception handling for file access errors
try:
    # Create a safe rotating file handler that won't crash on permission errors
    class SafeRotatingFileHandler(RotatingFileHandler):
        def doRollover(self):
            """
            Override doRollover to handle file permission errors gracefully
            """
            try:
                # Try the normal rollover
                super().doRollover()
            except (PermissionError, OSError) as e:
                # Log to console instead
                print(f"Warning: Could not rotate log file due to permission error: {str(e)}")
    
    # Create the handler with our safe implementation
    file_handler = SafeRotatingFileHandler(
        'logs/ifc_analyzer.log', 
        maxBytes=10240, 
        backupCount=10,
        delay=True  # Delay file opening until first log write
    )
    
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('IFC Analyzer startup')
    
except Exception as e:
    print(f"Warning: Could not set up file logging: {str(e)}")
    # Set up console logging as a fallback
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    console_handler.setLevel(logging.INFO)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('IFC Analyzer startup (console logging only)')

if __name__ == '__main__':
    # Run the application, allow connections from all interfaces for testing
    app.run(host='0.0.0.0', port=5000, debug=True) 