from app import create_app

# Create the Flask application
app = create_app()

# This is the entry point that Vercel will look for
if __name__ == '__main__':
    app.run(host='0.0.0.0') 