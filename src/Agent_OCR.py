import os
from dotenv import load_dotenv
import json
from mistralai import Mistral, DocumentURLChunk
load_dotenv()


def DocumentOCR(filename: str) -> str:
    """
    Processes OCR (Optical Character Recognition) on a given document file. This function
    uploads the file to a specified OCR service, processes it, and retrieves the extracted
    text in markdown format. The processed OCR data is also saved in JSON format to an
    intermediate directory.

    :param filename: The name of the file to process through OCR.
    :type filename: str
    :return: The extracted document content in markdown format.
    :rtype: str
    """
    raw_data_path = os.getenv("RAW_DATA_PATH", "Data/Intermediate/Client_Input_RAW/")
    intermediate_data_path = os.getenv(
        "INTERMEDIATE_DATA_PATH", "Data/Intermediate/Client_Input_OCR/"
    )

    # Validate API Key
    api_key = os.getenv("MISTRAL_API_KEY")
    if api_key is None:
        raise ValueError("MISTRAL_API_KEY not found in environment variables.")
    client = Mistral(api_key=api_key)

    # Read file and upload
    try:
        with open(os.path.join(raw_data_path, filename), "rb") as file_content:
            uploaded_file = client.files.upload(
                file={
                    "file_name": os.path.join(raw_data_path, filename),
                    "content": file_content,
                },
                purpose="ocr",
            )
    except Exception as e:
        raise RuntimeError(f"Error uploading file: {e}")

    # Get signed URL
    try:
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id)
    except Exception as e:
        raise RuntimeError(f"Error generating signed URL: {e}")

    # Process OCR
    try:
        pdf_response = client.ocr.process(
            document=DocumentURLChunk(document_url=signed_url.url),
            model="mistral-ocr-latest",
            include_image_base64=False,
        )
        response_dict = json.loads(pdf_response.model_dump_json())
    except Exception as e:
        raise RuntimeError(f"Error processing OCR: {e}")

    # Save processed OCR results
    base_filename, _ = os.path.splitext(filename)
    new_filename = f"{base_filename}.json"
    output_path = os.path.join(intermediate_data_path, new_filename)

    # Handle file saving
    try:
        if os.path.exists(output_path):
            os.remove(output_path)
        with open(output_path, "w") as f:
            json.dump(response_dict, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise RuntimeError(f"Error saving OCR result: {e}")

    # Combine markdown content
    chunk_content_string = "\n".join(chunk["markdown"] for chunk in response_dict["pages"])

    return chunk_content_string

def load_from_json(file_path:str) -> str:
    """
    Loads JSON data from the specified file path and processes the content
    to extract and combine markdown chunks into a single string. This is
    useful for handling structured JSON input where relevant content
    is stored in markdown chunks under specific keys.

    :param file_path: The file path of the JSON file to be loaded.
    :type file_path: str

    :return: A single string containing concatenated markdown content
        from the JSON data.
    :rtype: str
    """
    with open(file_path, "r") as f:
        data = json.load(f)

    chunk_content_string = "\n".join(chunk["markdown"] for chunk in data["pages"])
    return chunk_content_string