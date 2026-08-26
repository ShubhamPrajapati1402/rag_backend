from langchain_huggingface import HuggingFaceEndpointEmbeddings
from app.core.config import settings

def get_embeddings_model():
    """
    Initializes and returns the Hugging Face embeddings model via the Inference API.
    We are using the model defined in our .env (BAAI/bge-m3) which returns 1024-dimensional vectors.
    By using the Inference API, we don't have to download the massive model locally; Hugging Face does the math for us.
    """
    return HuggingFaceEndpointEmbeddings(
        huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY,
        repo_id=settings.HUGGINGFACE_EMBEDDING_MODEL
    )
