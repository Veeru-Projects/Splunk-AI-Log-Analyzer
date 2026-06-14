from splunklib.client import connect
import splunklib.results as results
import json
import asyncio
from splunklib.ai import Agent, GoogleModel
# from pydantic import BaseModel
from pprint import pprint
import time
import os

# Connect to Splunk
service = connect(
    scheme="https",
    host="veerender-mothukuri.com",
    port=443,
    username=os.getenv("username"),
    password=os.getenv("password"),
    autologin=True,
)

# Read Logs from Splunk using the search_query and return search_results
def read_logs_from_splunk():
    """Run a Splunk search and return JSON result records."""
    search_query = 'search index="portfolio" source="http:portfolio_logs" '
    print(f"Running Splunk search: {search_query}")

    kwargs_oneshot = {
        "earliest_time": "-7d",
        "latest_time": "now",
        "output_mode": "json",
    }

    results_oneshot = service.jobs.oneshot(search_query, **kwargs_oneshot)
    print("Splunk search response received.")

    reader = results.JSONResultsReader(results_oneshot)
    search_results = []

    for result in reader:
        if isinstance(result, dict):
            search_results.append(result)
            print("Result:", result)
        else:
            print("Message:", result)

    print(f"Total results found: {len(search_results)}")
    return search_results


# # Define the logs file
# logs_file = "logs.json"


# def write_logs_to_file(search_results, logs_file):
#     """Write Splunk results to a file with pretty-printed multi-line JSON."""
#     with open(logs_file, "w", encoding="utf-8") as f:
#         json.dump(search_results, f, indent=2, ensure_ascii=False)
#         f.write("\n")

#     print(f"Saved {len(search_results)} results to {logs_file}")



async def main(search_results):
    model = GoogleModel(
        model="gemini-3.5-flash",
        # model="gemini-2.5-flash",
        api_key=os.getenv("gcp_api_key"),
    )
    async with Agent(
        model=model,
        system_prompt="Your an AIOPS assistant that helps with Splunk queries and log data analysis for unusual patterns and anomalies and also threat detection.",
        service=service,
    ) as agent:
        payload = {
            "search_results": search_results,
        }
        result = await agent.invoke_with_data(
            instructions='Assess the Logs for any unusual patterns or potential threats. provide output in a structured format with insights and recommendations. Don\'t provide generic responses be specific to the data. Expect this ip "98.169.168.237" find any other ip addresses that are harmful.',
            data=payload,
        )
    return result

def format_result(result):
    load_result = str(result)
    key_word = "assistant"
    formatted_output = load_result.split(key_word, 1)[-1]
    formatted_output = formatted_output.replace("'", '"')
    formatted_output = formatted_output.replace("\\", "")
    formatted_output = formatted_output.strip('"')
    formatted_output = formatted_output.strip(", ")
    # print(formatted_output)
    # pprint(formatted_output, width=120, compact=False)
    return formatted_output

def store_result_in_kvstore(formatted_output, log_data):
    collection = service.kvstore["processed_output"]
    collection.data.delete()
    collection.data.insert(json.dumps({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "host":      log_data["host"],
        "data":   formatted_output,
        "severity": log_data["severity"],
        "category": log_data["category"]
    }))


if __name__ == "__main__":
    # read_logs_from_splunk()
    # write_logs_to_file(read_logs_from_splunk(), logs_file)
    asyncio.run(main(search_results=read_logs_from_splunk()))
    format_result(result=asyncio.run(main(search_results=read_logs_from_splunk())))
    store_result_in_kvstore(format_result(result=asyncio.run(main(search_results=read_logs_from_splunk()))), read_logs_from_splunk()[0])
