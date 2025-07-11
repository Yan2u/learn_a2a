from typing import List

from fastmcp import Context
import requests
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from typing_extensions import Annotated
from pydantic import Field
from net_simulator.utils import get_config
from pathlib import Path
from uuid import uuid4
import json

CWD = Path(__file__).parent
DATA_FILE = CWD.parent / 'data' / 'medical_records.json'


def main():
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text('{}')  # Initialize with an empty JSON object

    data = json.loads(DATA_FILE.read_text())

    mcp = FastMCP(
        name='Medical Record System',
        instructions="""The tool to interact with the medical record system. You can use this tool to get/update for medical records by ID.""")

    @mcp.tool()
    def get_medical_record(
            record_id: Annotated[str, Field(description='ID of the medical record to retrieve')],
    ) -> List[str]:
        """
        Retrieve a medical record by its ID.
        Returns a list of reports/diagnoses associated with the record ID.
        """
        if record_id not in data:
            raise ToolError(f"Medical record with ID {record_id} not found.")
        return data[record_id]

    @mcp.tool()
    def add_medical_record(
            record_id: Annotated[str, Field(description='ID of the medical record to add')],
            name: Annotated[str, Field(description='Name of the patient')],
            record: Annotated[str, Field(description='Brief description or report of a diagnosis or treatment')],
    ) -> str:
        """
        Add a new medical record with the given ID and data.
        """
        if record_id not in data:
            data[record_id] = {
                'name': name,
                'record': []
            }

        data[record_id]['record'].append(record)
        DATA_FILE.write_text(json.dumps(data, indent=4))
        return f"Medical record with ID {record_id} added successfully."

    @mcp.tool()
    def generate_medical_record_id() -> str:
        """
        Generate a new unique ID for a medical record.
        """
        return uuid4().hex

    @mcp.tool()
    def list_all_medical_records() -> dict:
        """
        List all medical records with their IDs and names.
        Returns a list of strings in the format "ID: Name".
        """
        return data

    port = get_config('mcp.medical_record_port')
    mcp.run(host='0.0.0.0', port=port, transport='sse')


if __name__ == '__main__':
    main()
