"""
Shared model cache to avoid loading the sentence transformer model multiple times.
Reduces startup time from 2s per script to 2s once.
"""

_model = None
_model_name = 'all-MiniLM-L6-v2'

def get_model():
    """
    Get or create the sentence transformer model.
    Only loads once, then returns cached instance.
    """
    global _model

    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("\nERROR: sentence-transformers not installed.")
            print("Install with: pip install -r requirements.txt")
            exit(1)

        _model = SentenceTransformer(_model_name)

    return _model

def get_model_name():
    """Return the model name being used."""
    return _model_name
