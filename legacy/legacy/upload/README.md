
## Classes

### 1. `MegaUploader`
- **Purpose**: Main entry point for uploading files to MEGA.
- **Description**: This class provides a simple interface for uploading files, setting file attributes, and retrieving upload results.
- **Key Methods**:
  - `upload`: Uploads a file to MEGA.

### 2. `UploadCoordinator`
- **Purpose**: Coordinates the entire MEGA upload process.
- **Description**: This class orchestrates the upload process by validating the file, obtaining an upload URL, dividing the file into chunks, managing parallel uploads, processing chunk encryption, and creating the final node in MEGA.
- **Key Methods**:
  - `upload`: Executes the complete upload process.
  - `_get_upload_url`: Obtains the upload URL from the MEGA API.
  - `_upload_file_chunks`: Uploads all file chunks with parallel processing.
  - `_process_and_upload_chunk`: Processes and uploads a single chunk.

### 3. `NodeCreator`
- **Purpose**: Handles creating nodes in MEGA after file uploads.
- **Description**: This class prepares node data for the MEGA API, encrypts file attributes, encrypts file keys, and sends node creation requests to MEGA.
- **Key Methods**:
  - `prepare_node_data`: Prepares data for creating a node in MEGA.
  - `create_node`: Creates a node in MEGA after a successful upload.

### 4. `ChunkUploader`
- **Purpose**: Handles the upload of individual chunks to the MEGA API.
- **Description**: This class prepares HTTP headers for chunk uploads, sends chunks to the MEGA server, and processes server responses.
- **Key Methods**:
  - `upload_chunk`: Uploads a chunk to the MEGA server.
  - `prepare_headers`: Prepares HTTP headers for chunk upload.

### 5. `FileReader`
- **Purpose**: Handles reading chunks from files for MEGA uploads.
- **Description**: This class opens files for reading, reads specific chunks from a file, and handles file I/O errors.
- **Key Methods**:
  - `read_chunk`: Reads a chunk from a file.

### 6. `FileValidator`
- **Purpose**: Handles file validation and preparation for MEGA uploads.
- **Description**: This class validates file existence and properties, converts file paths to Path objects, and retrieves file size information.
- **Key Methods**:
  - `validate_and_prepare`: Validates and prepares a file for upload.

### 7. `MegaChunkingStrategy`
- **Purpose**: Implements MEGA's specific chunking strategy for file uploads.
- **Description**: This class defines how to split files into chunks for MEGA uploads, using progressively larger chunks.
- **Key Methods**:
  - `calculate_chunks`: Calculates chunk boundaries for a file of the given size.

### 8. `CryptoHandler`
- **Purpose**: Handles encryption and MAC calculations for MEGA file uploads.
- **Description**: This class encrypts file chunks using AES-CTR, computes chunk MACs, and computes the final meta-MAC.
- **Key Methods**:
  - `encrypt_chunk`: Encrypts a chunk and calculates its MAC.
  - `compute_chunk_mac`: Computes the CBC-MAC for a chunk.
  - `compute_meta_mac`: Computes the meta-MAC from all chunk MACs.
  - `get_final_key`: Generates the final key for the upload.

## Example Usage

To see how to use the `MegaUploader` class, refer to the `example_usage.py` file. This script demonstrates how to upload a file to MEGA, including setting up the MEGA API client and handling file attributes.

## Requirements

- Python 3.12+
- `aiofiles`
- `pycryptodome`
- `aiohttp`

## Installation

To install the required packages, you can use pip:

```bash
pip install aiofiles pycryptodome aiohttp
```

## License

This project is licensed under the MIT License.