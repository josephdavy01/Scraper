import requests
import json

API_KEY = "8d917bdf-ee01-49eb-bb99-b7c5260377bf"
 
# 2. This is the URL to your local server.
API_URL = "http://34.28.211.104.nip.io:8787/tickets/api/create/"# Adjust if your Django runs elsewhere

def create_ticket(data):
    """
    Sends a POST request to the Django API to create a ticket.
    """
    # --- Set up Headers ---
    # This comes from your APIKeyAuthentication class
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": API_KEY
    }

    try:
        # --- Make the Request ---
        response = requests.post(API_URL, headers=headers, json=data)

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
        print(f"An error occurred while creating ticket: {e}")


def raise_ticket(step_name, function_name, details, country="Global"):
    print(f"Raising Ticket: [{step_name}] {function_name} - {details}")
    ticket_data = {
        "brand": "Berskha",
        "country": country,
        "step_name": step_name,
        "function_name": function_name,
        "details": details
    }
    create_ticket(ticket_data)