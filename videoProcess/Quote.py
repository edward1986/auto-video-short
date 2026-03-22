import requests
import json
import os
from dotenv import load_dotenv
# load environment constants
load_dotenv(".env")

# function to get the quote from the API 
# Get the information form the API
# Format the response
# Parse json  and return the single fact


def format_message(poem):
    poem_author = poem["author"]
    poem_title = poem["title"]
    poem_text = " "
    for line in poem["lines"]:
        poem_text += f"{line}\n"
    return f'Poem "{poem_title}" by {poem_author} - {poem_text}'


def fetch_poem(poet=""):
    if poet:
        url = f"https://poetrydb.org/author/{poet}/title,author,lines"
    else:
        url = "https://poetrydb.org/random/1/title,author,lines"

    return requests.get(url).json()[0]



def get_quote():
    fact_key = os.environ["FACT_KEY"]
    response = requests.request("GET", os.environ["FACT_URL"])
    formatted = response.text
    parse_json = json.loads(formatted)
    return parse_json[fact_key]
