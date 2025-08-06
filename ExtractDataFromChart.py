import websocket
import json
import time
import requests
import csv
import os

# Configuration
WS_URL = "ws://localhost:4848/app/"  # For Qlik Sense Desktop
APP_NAME = "YourApp.qvf"  # Replace with your app name (e.g., "Executive Dashboard.qvf")
CHART_ID = "kfxNpV"  # Replace with your chart ID (find via Dev-Hub or script output)
OUTPUT_CSV = "chart_data.csv"  # Output file for chart data

# Global variables to track handles and message IDs
app_handle = None
session_handle = None
chart_handle = None
hypercube_handle = None
message_id = 1
responses = {}

def on_message(ws, message):
    """Handle incoming WebSocket messages."""
    global app_handle, session_handle, chart_handle, hypercube_handle, message_id
    response = json.loads(message)
    print(f"Received response ID {response.get('id')}: {json.dumps(response, indent=2)}")
    responses[response["id"]] = response

    if response["id"] == 1:  # GetDocList
        # Find the app ID (path for Desktop, GUID for Enterprise)
        for doc in response["result"]["qDocList"]:
            if doc["qDocName"] == APP_NAME:
                app_id = doc["qDocId"]
                # Open the app
                send_request(ws, {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "handle": -1,
                    "method": "OpenDoc",
                    "params": [app_id]
                })

    elif response["id"] == 2:  # OpenDoc
        app_handle = response["result"]["qReturn"]["qHandle"]
        # Create session object for sheet list
        send_request(ws, {
            "jsonrpc": "2.0",
            "id": 3,
            "handle": app_handle,
            "method": "CreateSessionObject",
            "params": [{
                "qInfo": {"qType": "SheetList"},
                "qAppObjectListDef": {
                    "qType": "sheet",
                    "qData": {"cells": "/cells"}
                }
            }]
        })

    elif response["id"] == 3:  # CreateSessionObject (SheetList)
        session_handle = response["result"]["qReturn"]["qHandle"]
        # Get sheet layout to list charts
        send_request(ws, {
            "jsonrpc": "2.0",
            "id": 4,
            "handle": session_handle,
            "method": "GetLayout",
            "params": []
        })

    elif response["id"] == 4:  # GetLayout (SheetList)
        # List charts (optional: for debugging or finding chart IDs)
        sheets = response["result"]["qLayout"]["qAppObjectList"]["qItems"]
        for sheet in sheets:
            for cell in sheet["qData"]["cells"]:
                print(f"Chart ID: {cell['name']}, Type: {cell['type']}")
        # Get the chart object
        send_request(ws, {
            "jsonrpc": "2.0",
            "id": 5,
            "handle": app_handle,
            "method": "GetObject",
            "params": [CHART_ID]
        })

    elif response["id"] == 5:  # GetObject (Chart)
        chart_handle = response["result"]["qReturn"]["qHandle"]
        # Get chart layout to extract HyperCubeDef
        send_request(ws, {
            "jsonrpc": "2.0",
            "id": 6,
            "handle": chart_handle,
            "method": "GetLayout",
            "params": []
        })

    elif response["id"] == 6:  # GetLayout (Chart)
        hypercube_def = response["result"]["qLayout"]["qHyperCubeDef"]
        # Create a HyperCube session object to fetch data
        send_request(ws, {
            "jsonrpc": "2.0",
            "id": 7,
            "handle": app_handle,
            "method": "CreateSessionObject",
            "params": [{
                "qInfo": {"qType": "HyperCube"},
                "qHyperCubeDef": {
                    "qDimensions": hypercube_def["qDimensions"],
                    "qMeasures": hypercube_def["qMeasures"],
                    "qInitialDataFetch": [{"qTop": 0, "qLeft": 0, "qHeight": 1000, "qWidth": len(hypercube_def["qDimensions"]) + len(hypercube_def["qMeasures"])}]
                }
            }]
        })

    elif response["id"] == 7:  # CreateSessionObject (HyperCube)
        hypercube_handle = response["result"]["qReturn"]["qHandle"]
        # Get HyperCube data
        send_request(ws, {
            "jsonrpc": "2.0",
            "id": 8,
            "handle": hypercube_handle,
            "method": "GetLayout",
            "params": []
        })

    elif response["id"] == 8:  # GetLayout (HyperCube)
        # Extract and save chart data
        hypercube = response["result"]["qLayout"]["qHyperCube"]
        dimensions = [dim["qDef"]["qFieldDefs"][0] for dim in hypercube["qDimensionInfo"]]
        measures = [meas["qDef"]["qLabel"] or meas["qDef"]["qDef"] for meas in hypercube["qMeasureInfo"]]
        data = hypercube["qDataPages"][0]["qMatrix"]

        # Write to CSV
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            # Write header
            writer.writerow(dimensions + measures)
            # Write data rows
            for row in data:
                row_data = [cell["qText"] for cell in row]
                writer.writerow(row_data)
        print(f"Chart data saved to {OUTPUT_CSV}")

        # Optionally, export as file (Excel/CSV) using ExportData
        send_request(ws, {
            "jsonrpc": "2.0",
            "id": 9,
            "handle": chart_handle,
            "method": "ExportData",
            "params": ["CSV_C"]
        })

    elif response["id"] == 9:  # ExportData
        export_url = "http://localhost:4848" + response["result"]["qUrl"]
        response = requests.get(export_url, allow_redirects=True)
        with open("exported_chart_data.csv", "wb") as f:
            f.write(response.content)
        print("Exported chart data saved to exported_chart_data.csv")
        ws.close()  # Close WebSocket connection

def on_error(ws, error):
    """Handle WebSocket errors."""
    print(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    """Handle WebSocket close."""
    print("WebSocket connection closed")

def on_open(ws):
    """Handle WebSocket open."""
    print("Connected to Qlik Engine")
    # Start by getting the list of apps
    send_request(ws, {
        "jsonrpc": "2.0",
        "id": 1,
        "handle": -1,
        "method": "GetDocList",
        "params": []
    })

def send_request(ws, request):
    """Send a JSON-RPC request with incremented message ID."""
    global message_id
    request["id"] = message_id
    ws.send(json.dumps(request))
    message_id += 1

def main():
    # Set up WebSocket
    ws = websocket.WebSocketApp(
        WS_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    # Run WebSocket in a loop with reconnection handling
    ws.run_forever()

if __name__ == "__main__":
    main()
