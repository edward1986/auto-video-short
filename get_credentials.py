import pickle
import google_auth_oauthlib.flow

CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CREDENTIALS_FILE = "credentials.pickle"

def get_credentials():
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)

    with open(CREDENTIALS_FILE, "wb") as token:
        pickle.dump(credentials, token)

    print("Refresh token:", credentials.refresh_token)

get_credentials()
