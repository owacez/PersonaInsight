import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize


class TextPreprocessor:
    """Text preprocessing class for cleaning and normalizing text data"""

    def __init__(self):
        """Initialize the TextPreprocessor with necessary NLTK components"""
        try:
            # Download required NLTK data if not already present
            self._download_nltk_data()

            # Initialize lemmatizer
            self.lemmatizer = WordNetLemmatizer()

            # Load stopwords
            try:
                self.stop_words = set(stopwords.words('english'))
            except LookupError:
                nltk.download('stopwords', quiet=True)
                self.stop_words = set(stopwords.words('english'))

            print("TextPreprocessor initialized successfully")

        except Exception as e:
            print(f"Error initializing TextPreprocessor: {str(e)}")
            # Set default values to prevent AttributeError
            self.lemmatizer = WordNetLemmatizer()
            self.stop_words = set()
            raise

    def _download_nltk_data(self):
        """Download required NLTK data packages"""
        required_packages = ['punkt', 'stopwords', 'wordnet', 'omw-1.4', 'punkt_tab']

        for package in required_packages:
            try:
                nltk.data.find(f'tokenizers/{package}')
            except LookupError:
                try:
                    nltk.data.find(f'corpora/{package}')
                except LookupError:
                    print(f"Downloading {package}...")
                    nltk.download(package, quiet=True)

    def preprocess_text(self, text):
        """
        Preprocess text by cleaning, tokenizing, removing stopwords, and lemmatizing

        Args:
            text (str): Raw text to preprocess

        Returns:
            str: Preprocessed text
        """
        try:
            # Input validation
            if not text or not isinstance(text, str):
                return ""

            # Convert to lowercase
            text = text.lower()

            # Remove URLs
            text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)

            # Remove user mentions and hashtags
            text = re.sub(r'@\w+|#\w+', '', text)

            # Remove special characters and numbers, keep only letters and spaces
            text = re.sub(r'[^a-zA-Z\s]', '', text)

            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text).strip()

            # Tokenize
            try:
                tokens = word_tokenize(text)
            except LookupError:
                # Fallback to simple split if word_tokenize fails
                nltk.download('punkt', quiet=True)
                tokens = word_tokenize(text)

            # Remove stopwords and lemmatize
            processed_tokens = []
            for token in tokens:
                if token not in self.stop_words and len(token) > 2:
                    # Lemmatize the token
                    lemmatized = self.lemmatizer.lemmatize(token)
                    processed_tokens.append(lemmatized)

            # Join tokens back into string
            processed_text = ' '.join(processed_tokens)

            return processed_text

        except AttributeError as e:
            print(f"Error preprocessing text: {str(e)}")
            # Re-initialize lemmatizer if it's missing
            if not hasattr(self, 'lemmatizer'):
                self.lemmatizer = WordNetLemmatizer()
            return text  # Return original text as fallback

        except Exception as e:
            print(f"Error preprocessing text: {str(e)}")
            return text  # Return original text as fallback

    def batch_preprocess(self, texts):
        """
        Preprocess multiple texts

        Args:
            texts (list): List of texts to preprocess

        Returns:
            list: List of preprocessed texts
        """
        try:
            if not texts:
                return []

            return [self.preprocess_text(text) for text in texts]

        except Exception as e:
            print(f"Error in batch preprocessing: {str(e)}")
            return texts  # Return original texts as fallback


# Test the preprocessor
if __name__ == "__main__":
    # Initialize preprocessor
    preprocessor = TextPreprocessor()

    # Test texts
    test_texts = [
        "I absolutely LOVE this new product! Best purchase ever! 🎉",
        "Check out this link: https://example.com #awesome @user123",
        "This is a simple sentence for testing purposes.",
        "Running, jumping, and playing are all fun activities!"
    ]

    print("\n=== Testing TextPreprocessor ===\n")

    for i, text in enumerate(test_texts, 1):
        print(f"Original {i}: {text}")
        processed = preprocessor.preprocess_text(text)
        print(f"Processed {i}: {processed}\n")

    # Test batch processing
    print("=== Batch Processing ===")
    batch_results = preprocessor.batch_preprocess(test_texts)
    for i, result in enumerate(batch_results, 1):
        print(f"{i}. {result}")