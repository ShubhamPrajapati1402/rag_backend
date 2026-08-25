from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
from app.core.config import settings

def get_embeddings_model():
    """
    Initializes and returns the Hugging Face embeddings model via the Inference API.
    We are using the model defined in our .env (BAAI/bge-m3) which returns 1024-dimensional vectors.
    By using the Inference API, we don't have to download the massive model locally; Hugging Face does the math for us.
    """
    return HuggingFaceInferenceAPIEmbeddings(
        api_key=settings.HUGGINGFACE_API_KEY,
        model_name=settings.HUGGINGFACE_EMBEDDING_MODEL
    )
