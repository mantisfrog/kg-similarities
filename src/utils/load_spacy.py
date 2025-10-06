import spacy
import subprocess

def load_spacy_model(model_name="en_core_web_md"):
    """
    Loads a spaCy model, downloading it if it's not already installed.

    Args:
        model_name (str): The name of the spaCy model to load.

    Returns:
        spacy.Language: The loaded spaCy language model.
    """
    try:
        nlp = spacy.load(model_name)
    except OSError:
        print(f"Downloading spaCy model '{model_name}'...")
        subprocess.run(["python", "-m", "spacy", "download", model_name], check=True)
        nlp = spacy.load(model_name)
    return nlp