import requests
import json
 
# --- Configuration ---
API_KEY = "8d917bdf-ee01-49eb-bb99-b7c5260377bf"
 
# 2. This is the URL to your local server.
API_URL = "http://34.28.211.104.nip.io:8787/tickets/api/create/"
 
# --- Set up Headers ---
# This comes from your APIKeyAuthentication class
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": API_KEY
}
 
# --- Data to Send ---
# These fields come from your TicketCreateSerializer
'''
ticket_data = {
    "brand": "Python Script",
    "country": "IND",
    "step_name": "API Test",
    "function_name": "create_ticket_test",
    "details": "This is a test ticket created from a Python script."
}
'''
 
# --- Make the Request ---
def create_ticket(ticket_data):
    try:
        response = requests.post(
            API_URL,
            headers=headers,
            data=json.dumps(ticket_data)
        )
 
        # --- Handle the Response ---
        if response.status_code == 201:
            # 201 CREATED (Success)
            response_data = response.json()
            print(f"✅ Success! Ticket created with ID: {response_data.get('ticket_id')}")
           
        elif response.status_code == 401:
            # 401 UNAUTHORIZED
            print(f"❌ Error: Authentication Failed. Is your API_KEY correct?")
            print(f"Response: {response.json()}")
 
        elif response.status_code == 400:
            # 400 BAD REQUEST (e.g., missing fields)
            print(f"❌ Error: Invalid data. The server returned:")
            print(response.json())
           
        else:
            # Other errors (e.g., 500 Server Error)
            print(f"❌ An unexpected error occurred (HTTP {response.status_code}):")
            print(response.text)
 
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to {API_URL}.")
        print("Is your Django server running?")
    except Exception as e:
        print(f"An error occurred: {e}")


def raise_ticket(step_name, function_name, details, country="Global"):
    ticket_data = {
        "brand": "Alo Yoga",
        "country": country,
        "step_name": step_name,
        "function_name": function_name,
        "details": details
    }
    create_ticket(ticket_data)