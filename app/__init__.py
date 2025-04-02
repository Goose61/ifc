import os
from flask import Flask, render_template
from flask_cors import CORS
from turbo_flask import Turbo

# Initialize Turbo-Flask outside app context for global access
turbo = Turbo()

def create_app(test_config=None):
    """Create and configure the Flask application."""
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Enable CORS
    CORS(app)
    
    # Initialize Turbo-Flask with our app
    turbo.init_app(app)
    
    # Set default configuration
    app.config.from_mapping(
        SECRET_KEY='dev',
        UPLOAD_FOLDER=os.path.join(os.getcwd(), 'app', 'uploads'),
        ALLOWED_EXTENSIONS={'ifc'},
        MAX_CONTENT_LENGTH=100 * 1024 * 1024,  # 100MB max upload
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register blueprints
    from app.routes import main, api, errors
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(errors.bp)

    # Register error handlers
    from app.routes.errors import not_found_error, internal_error, forbidden_error, too_large_error, bad_request_error
    app.register_error_handler(404, not_found_error)
    app.register_error_handler(500, internal_error)
    app.register_error_handler(403, forbidden_error)
    app.register_error_handler(413, too_large_error)
    app.register_error_handler(400, bad_request_error)

    # Add a health check route
    @app.route('/health')
    def health_check():
        return {'status': 'ok'}, 200

    return app 