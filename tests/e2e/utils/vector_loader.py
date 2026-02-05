"""
VectorLoader - Load and parse JSON test vectors for E2E testing.

Test vectors are stored in tests/e2e/vectors/ organized by category.
Each vector file contains test cases that can be used to validate
protocol conformance across different implementations.
"""

import json
import os
from pathlib import Path


class VectorLoader:
    """
    Loads and manages test vectors from JSON files.

    Vector files are organized by category:
    - crypto/    - Cryptographic operation vectors
    - packets/   - Packet encoding/decoding vectors
    - resource/  - Resource transfer vectors
    - channel/   - Channel messaging vectors
    - identity/  - Identity and key vectors
    """

    def __init__(self, base_path=None):
        """
        Initialize the vector loader.

        :param base_path: Base path to vectors directory. If None, uses
                          tests/e2e/vectors relative to this file.
        """
        if base_path is None:
            # Default to vectors directory relative to this file
            self.base_path = Path(__file__).parent.parent / "vectors"
        else:
            self.base_path = Path(base_path)

    def load(self, category, name):
        """
        Load a complete vector file.

        :param category: Vector category (e.g., "crypto", "packets")
        :param name: Vector file name without .json extension
        :returns: Parsed JSON content
        :raises: FileNotFoundError if vector file doesn't exist
        """
        vector_path = self.base_path / category / f"{name}.json"
        if not vector_path.exists():
            raise FileNotFoundError(f"Vector file not found: {vector_path}")

        with open(vector_path, "r") as f:
            return json.load(f)

    def iter_vectors(self, category, name):
        """
        Iterate over individual test vectors in a file.

        Expected file format:
        {
            "description": "...",
            "vectors": [
                {"id": "...", "input": {...}, "expected": {...}},
                ...
            ]
        }

        :param category: Vector category
        :param name: Vector file name
        :yields: Individual vector dictionaries
        """
        data = self.load(category, name)
        vectors = data.get("vectors", [])
        for vector in vectors:
            yield vector

    def get_vector_by_id(self, category, name, vector_id):
        """
        Get a specific vector by its ID.

        :param category: Vector category
        :param name: Vector file name
        :param vector_id: ID of the vector to retrieve
        :returns: Vector dictionary or None if not found
        """
        for vector in self.iter_vectors(category, name):
            if vector.get("id") == vector_id:
                return vector
        return None

    def list_categories(self):
        """
        List available vector categories.

        :returns: List of category names
        """
        if not self.base_path.exists():
            return []
        return [d.name for d in self.base_path.iterdir() if d.is_dir()]

    def list_vectors(self, category):
        """
        List available vector files in a category.

        :param category: Category to list
        :returns: List of vector file names (without .json extension)
        """
        category_path = self.base_path / category
        if not category_path.exists():
            return []
        return [f.stem for f in category_path.glob("*.json")]

    def get_metadata(self, category, name):
        """
        Get metadata from a vector file.

        :param category: Vector category
        :param name: Vector file name
        :returns: Dictionary with description and other metadata
        """
        data = self.load(category, name)
        return {
            "description": data.get("description", ""),
            "version": data.get("version", "1.0"),
            "count": len(data.get("vectors", []))
        }

    @staticmethod
    def hex_to_bytes(hex_string):
        """
        Convert a hex string to bytes.
        Handles both with and without 0x prefix.

        :param hex_string: Hex string to convert
        :returns: Bytes
        """
        if hex_string.startswith("0x"):
            hex_string = hex_string[2:]
        return bytes.fromhex(hex_string)

    @staticmethod
    def bytes_to_hex(data):
        """
        Convert bytes to hex string.

        :param data: Bytes to convert
        :returns: Hex string
        """
        return data.hex()


class VectorGenerator:
    """
    Helper class to generate test vectors from the reference implementation.
    Used to create the initial vector files.
    """

    def __init__(self, output_path=None):
        """
        Initialize the vector generator.

        :param output_path: Path to write generated vectors
        """
        if output_path is None:
            self.output_path = Path(__file__).parent.parent / "vectors"
        else:
            self.output_path = Path(output_path)

    def save(self, category, name, description, vectors, version="1.0"):
        """
        Save generated vectors to a file.

        :param category: Vector category
        :param name: Vector file name
        :param description: Description of the vector set
        :param vectors: List of vector dictionaries
        :param version: Vector format version
        """
        category_path = self.output_path / category
        category_path.mkdir(parents=True, exist_ok=True)

        data = {
            "description": description,
            "version": version,
            "vectors": vectors
        }

        output_file = category_path / f"{name}.json"
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        return output_file
