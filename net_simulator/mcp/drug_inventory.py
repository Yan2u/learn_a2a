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
DATA_FILE = CWD.parent / 'data' / 'drug_inventory.json'


def main():
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text('[]')  # Initialize with an empty JSON object

    data = json.loads(DATA_FILE.read_text())

    mcp = FastMCP(
        name='Drug Inventory System',
        instructions="""The tool to interact with the drug inventory system. You can use this tool to record the drugs consumed by prescriptions.""")

    @mcp.tool()
    def add_expense_item(
            item: Annotated[str, Field(description='Name of the drug or item consumed')],
            amount: Annotated[str, Field(description='Amount of the drug or item consumed')],
    ):
        """
        Add a new expense item to the drug inventory.
        """
        data.append({
            'name': item,
            'amount': amount,
        })
        DATA_FILE.write_text(json.dumps(data, indent=4))
        return f"Expense item '{item}' with amount '{amount}' added successfully."

    @mcp.tool()
    def get_expense_items() -> List[dict]:
        """
        Retrieve all expense items from the drug inventory.
        Returns a list of dictionaries containing item names and amounts.
        """
        if not data:
            raise ToolError("No expense items found in the inventory.")
        return data

    port = get_config('mcp.drug_inventory_port')
    mcp.run(host='0.0.0.0', port=port, transport='sse')


if __name__ == '__main__':
    main()
