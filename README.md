# IFC Analyzer Web Application

A web-based application for analyzing IFC (Industry Foundation Classes) files and generating detailed material takeoff reports.

## Features

- Upload and analyze IFC2X3 files
- Extract comprehensive material information from IFC elements
- Calculate volumes, areas, and dimensions
- Generate detailed reports in multiple formats (Excel, CSV, JSON)
- Web-based interface for easy access
- API endpoints for integration with other systems

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/ifc-analyzer.git
cd ifc-analyzer
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Access the web interface at `http://localhost:5000`

## Requirements

- Python 3.8 or higher
- ifcopenshell 0.7.0 or higher
- Flask 2.2.0 or higher
- Other dependencies listed in requirements.txt

## Usage

1. Open the application in your web browser
2. Upload an IFC2X3 file using the file upload form
3. Wait for the analysis to complete
4. View the results and download reports in your preferred format

## Project Structure

```
ifc-analyzer/
├── app/                    # Main application package
│   ├── models/             # Data models and analysis tools
│   │   ├── material_takeoff.py  # Material takeoff analyzer
│   │   └── ifc_database.py      # Database interactions
│   ├── routes/             # Web routes
│   │   ├── main.py         # Main web routes
│   │   └── api.py          # API endpoints
│   ├── static/             # Static files
│   │   ├── css/            # CSS files
│   │   └── js/             # JavaScript files
│   ├── templates/          # HTML templates
│   │   ├── base.html       # Base template
│   │   ├── index.html      # Homepage
│   │   └── results.html    # Results page
│   ├── uploads/            # Directory for uploaded files
│   └── __init__.py         # Application factory
├── app.py                  # Application entry point
├── requirements.txt        # Dependencies
└── README.md               # Documentation
```

## API Endpoints

- `POST /api/upload` - Upload an IFC file
- `GET /api/analyze/<filename>` - Analyze an uploaded IFC file
- `GET /api/results/<filename>` - Retrieve analysis results

## Supported IFC Elements

- Walls
- Slabs
- Columns
- Beams
- Footings
- Windows
- Doors
- And many more...

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 