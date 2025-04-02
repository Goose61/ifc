import sqlite3
import json
from datetime import datetime
import os

class IFCDatabase:
    def __init__(self, db_path="ifc_data.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.initialize_database()

    def initialize_database(self):
        """Initialize the database with required tables."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        # Create tables
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS ifc_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                schema TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS elements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ifc_file_id INTEGER,
                element_type TEXT NOT NULL,
                global_id TEXT,
                name TEXT,
                description TEXT,
                volume REAL,
                area REAL,
                length REAL,
                width REAL,
                height REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ifc_file_id) REFERENCES ifc_files(id)
            );

            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                element_id INTEGER,
                name TEXT NOT NULL,
                material_type TEXT,
                category TEXT,
                description TEXT,
                grade TEXT,
                specification TEXT,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (element_id) REFERENCES elements(id)
            );

            CREATE TABLE IF NOT EXISTS material_takeoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ifc_file_id INTEGER,
                element_type TEXT NOT NULL,
                material_name TEXT NOT NULL,
                count INTEGER,
                total_volume REAL,
                total_area REAL,
                avg_length REAL,
                avg_width REAL,
                avg_height REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ifc_file_id) REFERENCES ifc_files(id)
            );
        ''')
        self.conn.commit()

    def store_ifc_file(self, file_path, schema):
        """Store IFC file information."""
        file_name = os.path.basename(file_path)
        self.cursor.execute('''
            INSERT INTO ifc_files (file_path, file_name, schema)
            VALUES (?, ?, ?)
        ''', (file_path, file_name, schema))
        self.conn.commit()
        return self.cursor.lastrowid

    def store_element(self, ifc_file_id, element_data):
        """Store element information."""
        self.cursor.execute('''
            INSERT INTO elements (
                ifc_file_id, element_type, global_id, name, description,
                volume, area, length, width, height
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ifc_file_id,
            element_data['type'],
            element_data.get('global_id'),
            element_data.get('name'),
            element_data.get('description'),
            element_data.get('volume'),
            element_data.get('area'),
            element_data.get('length'),
            element_data.get('width'),
            element_data.get('height')
        ))
        element_id = self.cursor.lastrowid
        self.conn.commit()
        return element_id

    def store_material(self, element_id, material_data):
        """Store material information."""
        self.cursor.execute('''
            INSERT INTO materials (
                element_id, name, material_type, category, description,
                grade, specification, properties
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            element_id,
            material_data['name'],
            material_data.get('material_type'),
            material_data.get('category'),
            material_data.get('description'),
            material_data.get('grade'),
            material_data.get('specification'),
            json.dumps(material_data.get('properties', {}))
        ))
        self.conn.commit()

    def store_material_takeoff(self, ifc_file_id, takeoff_data):
        """Store material takeoff information."""
        self.cursor.execute('''
            INSERT INTO material_takeoffs (
                ifc_file_id, element_type, material_name, count,
                total_volume, total_area, avg_length, avg_width, avg_height
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ifc_file_id,
            takeoff_data['element_type'],
            takeoff_data['material_name'],
            takeoff_data['count'],
            takeoff_data['total_volume'],
            takeoff_data['total_area'],
            takeoff_data.get('avg_length'),
            takeoff_data.get('avg_width'),
            takeoff_data.get('avg_height')
        ))
        self.conn.commit()

    def get_material_takeoff(self, ifc_file_id):
        """Retrieve material takeoff data for a specific IFC file."""
        self.cursor.execute('''
            SELECT element_type, material_name, count, total_volume,
                   total_area, avg_length, avg_width, avg_height
            FROM material_takeoffs
            WHERE ifc_file_id = ?
            ORDER BY element_type, material_name
        ''', (ifc_file_id,))
        return self.cursor.fetchall()

    def get_element_materials(self, element_id):
        """Retrieve materials for a specific element."""
        self.cursor.execute('''
            SELECT name, material_type, category, description,
                   grade, specification, properties
            FROM materials
            WHERE element_id = ?
        ''', (element_id,))
        return self.cursor.fetchall()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None 