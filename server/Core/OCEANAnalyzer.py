import nltk
import pandas as pd
import pickle
import os
import traceback
from sklearn.model_selection import train_test_split
from tensorflow.keras import layers, optimizers, preprocessing
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras import metrics
from Core.TextPreProcessor import TextPreprocessor
from Core.PersonalityInterpretor import PersonalityInterpreter


def download_nltk_resources():
    try:
        resources = ['punkt', 'stopwords', 'wordnet', 'omw-1.4']
        for resource in resources:
            nltk.download(resource, quiet=True)
            print(f"Successfully downloaded {resource}")
    except Exception as e:
        print(f"Error downloading NLTK resources: {str(e)}")


class OceanAnalyzer:
    def __init__(self, preprocessor, max_length=50):
        self.preprocessor = preprocessor
        self.max_length = max_length
        self.model = None
        self.tokenizer = preprocessing.text.Tokenizer()
        self.model_file = '../ocean_model.keras'
        self.tokenizer_file = '../ocean_tokenizer.pkl'
        self.interpreter = PersonalityInterpreter()

    def save_model(self):
        try:
            # Save the Keras model with the newer .keras format
            self.model.save(self.model_file, save_format='keras')
            # Save the tokenizer
            with open(self.tokenizer_file, 'wb') as f:
                pickle.dump(self.tokenizer, f)
            print("OCEAN model saved successfully")
        except Exception as e:
            print(f"Error saving model: {str(e)}")
            raise

    def load_model(self):
        if os.path.exists(self.model_file) and os.path.exists(self.tokenizer_file):
            try:
                # Load the Keras model
                self.model = load_model(self.model_file)
                # Load the tokenizer
                with open(self.tokenizer_file, 'rb') as f:
                    self.tokenizer = pickle.load(f)
                print("OCEAN model loaded successfully")
                return True
            except Exception as e:
                print(f"Error loading OCEAN model: {str(e)}")
                return False
        return False

    def build_model(self, vocab_size):
        try:
            model = Sequential([
                layers.Embedding(vocab_size, 50, input_length=self.max_length),
                layers.LSTM(64, return_sequences=True),
                layers.GlobalMaxPooling1D(),
                layers.Dense(32, activation='relu'),
                layers.Dense(5, activation='linear')
            ])
            model.compile(
                optimizer=optimizers.Adam(learning_rate=0.001),
                loss='mean_squared_error',
                metrics=[metrics.MeanSquaredError()]
            )
            return model
        except Exception as e:
            print(f"Error building model: {str(e)}")
            raise

    def load_data(self, filepath):
        print("Loading OCEAN dataset...")
        encodings = ['utf-8', 'iso-8859-1', 'cp1252', 'latin1']

        for encoding in encodings:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                print(f"Successfully loaded OCEAN data using {encoding} encoding.")
                return df
            except UnicodeDecodeError:
                continue

        raise Exception("Failed to load OCEAN dataset with any encoding.")

    def prepare_data(self, df):
        try:
            sentences = df['STATUS'].values
            labels = df[['sEXT', 'sNEU', 'sAGR', 'sCON', 'sOPN']].values

            self.tokenizer.fit_on_texts(sentences)
            X = self.tokenizer.texts_to_sequences(sentences)
            X = preprocessing.sequence.pad_sequences(X, maxlen=self.max_length)

            return train_test_split(X, labels, test_size=0.2, random_state=42)
        except Exception as e:
            print(f"Error preparing data: {str(e)}")
            raise

    def train(self, X_train, y_train, X_test, y_test, epochs=5, batch_size=64, save_model=True):
        try:
            print("\nTraining OCEAN analyzer...")
            vocab_size = len(self.tokenizer.word_index) + 1
            self.model = self.build_model(vocab_size)

            history = self.model.fit(
                X_train, y_train,
                epochs=epochs,
                batch_size=batch_size,
                validation_data=(X_test, y_test),
                verbose=1
            )
            print("OCEAN training completed")
            if save_model:
                self.save_model()
            return history
        except Exception as e:
            print(f"Error during training: {str(e)}")
            raise

    def analyze(self, texts):
        """
        Analyze texts and return OCEAN personality scores
        Fixed version to match Flask app expectations
        """
        try:
            # Initialize results list to prevent UnboundLocalError
            results = []

            # Input validation
            if not texts:
                raise ValueError("No texts provided for analysis")

            # Ensure texts is a list
            if isinstance(texts, str):
                texts = [texts]

            # Filter out empty texts
            valid_texts = [text for text in texts if text and isinstance(text, str) and text.strip()]

            if not valid_texts:
                raise ValueError("No valid texts provided for analysis")

            # Check if model is loaded
            if self.model is None:
                raise RuntimeError("Model not loaded. Please load or train a model first.")

            # Convert texts to sequences
            sequences = self.tokenizer.texts_to_sequences(valid_texts)

            # Pad sequences
            padded_sequences = preprocessing.sequence.pad_sequences(
                sequences, maxlen=self.max_length
            )

            # Make predictions
            predictions = self.model.predict(padded_sequences, verbose=0)

            # Process predictions into the format expected by Flask app
            for i, (text, pred) in enumerate(zip(valid_texts, predictions)):
                # Ensure prediction has 5 values for OCEAN traits
                if len(pred) != 5:
                    raise ValueError(f"Model prediction has {len(pred)} values, expected 5 for OCEAN traits")

                # Create result in the format expected by Flask app
                result = {
                    'text_index': i,
                    'text': text,
                    # Map to the trait names expected by Flask app
                    'extraversion': float(pred[0]),
                    'neuroticism': float(pred[1]),
                    'agreeableness': float(pred[2]),
                    'conscientiousness': float(pred[3]),
                    'openness': float(pred[4])
                }
                results.append(result)

            return results

        except Exception as e:
            print(f"Error in analyze method: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Analysis failed: {str(e)}")

    def calculate_average_scores(self, results):
        """
        Calculate average OCEAN scores across multiple text samples.
        Fixed to work with the new result format
        """
        try:
            if not results:
                raise ValueError("No results provided for averaging")

            # Initialize counters
            total_scores = {
                'extraversion': 0.0,
                'neuroticism': 0.0,
                'agreeableness': 0.0,
                'conscientiousness': 0.0,
                'openness': 0.0
            }

            valid_count = 0

            # Sum all scores
            for result in results:
                if isinstance(result, dict):
                    # Skip results with errors
                    if 'error' in result:
                        continue

                    # Add scores for each trait
                    for trait in total_scores.keys():
                        if trait in result and isinstance(result[trait], (int, float)):
                            total_scores[trait] += result[trait]

                    valid_count += 1

            if valid_count == 0:
                raise ValueError("No valid results for averaging")

            # Calculate averages
            average_scores = {
                trait: round(score / valid_count, 4)
                for trait, score in total_scores.items()
            }

            return average_scores

        except Exception as e:
            print(f"Error calculating average scores: {str(e)}")
            raise RuntimeError(f"Failed to calculate averages: {str(e)}")

    def generate_personality_summary(self, results):
        """
        Generate a complete personality summary based on multiple text analyses.
        Fixed to work with the new result format
        """
        try:
            # Calculate average scores
            average_scores = self.calculate_average_scores(results)
            if not average_scores:
                return "Insufficient data to generate a personality profile."

            # Use the interpreter if available, otherwise generate basic summary
            if hasattr(self, 'interpreter') and self.interpreter:
                try:
                    summary = self.interpreter.generate_personality_summary(average_scores)
                    return summary
                except Exception as interpreter_error:
                    print(f"Interpreter error: {str(interpreter_error)}")
                    # Fall back to basic summary

            # Generate basic summary if interpreter fails or is not available
            return self._generate_basic_summary(average_scores, len(results))

        except Exception as e:
            print(f"Error generating personality summary: {str(e)}")
            return f"Summary generation failed: {str(e)}"

    def _generate_basic_summary(self, average_scores, num_texts):
        """Generate a basic personality summary when interpreter is not available"""
        try:
            summary_parts = []

            summary_parts.append("Based on the analyzed text, this personality profile reveals someone who:")

            # Interpret each trait
            for trait, score in average_scores.items():
                if score > 0.6:
                    if trait == 'extraversion':
                        summary_parts.append("• Shows high extraversion - outgoing and energetic in social situations")
                    elif trait == 'neuroticism':
                        summary_parts.append(
                            "• Displays higher neuroticism - may experience more emotional variability")
                    elif trait == 'agreeableness':
                        summary_parts.append("• Demonstrates high agreeableness - cooperative and trusting")
                    elif trait == 'conscientiousness':
                        summary_parts.append("• Exhibits strong conscientiousness - organized and goal-directed")
                    elif trait == 'openness':
                        summary_parts.append("• Shows high openness - creative and open to new experiences")
                elif score < 0.4:
                    if trait == 'extraversion':
                        summary_parts.append("• Shows more introverted tendencies - prefers quieter environments")
                    elif trait == 'neuroticism':
                        summary_parts.append("• Displays emotional stability - generally calm under pressure")
                    elif trait == 'agreeableness':
                        summary_parts.append("• Shows more competitive tendencies - direct in interactions")
                    elif trait == 'conscientiousness':
                        summary_parts.append("• Exhibits more flexible approach - adaptable to changing situations")
                    elif trait == 'openness':
                        summary_parts.append(
                            "• Prefers conventional approaches - values tradition and established methods")
                else:
                    summary_parts.append(f"• Shows balanced {trait} - moderate levels across situations")

            summary_parts.append(f"\nAdditional insights:")
            summary_parts.append(f"• Analysis based on {num_texts} text samples")
            summary_parts.append(
                "• Scores range from 0.0 to 1.0, with higher scores indicating stronger trait expression")

            return "\n".join(summary_parts)

        except Exception as e:
            return f"Basic summary generation failed: {str(e)}"


def main():
    try:
        preprocessor = TextPreprocessor()
        ocean_analyzer = OceanAnalyzer(preprocessor)

        # Try to load existing model first
        model_loaded = ocean_analyzer.load_model()

        if not model_loaded:
            print("OCEAN model not found. Training new model...")
            ocean_df = ocean_analyzer.load_data('mypersonality_final.csv')
            X_train, X_test, y_train, y_test = ocean_analyzer.prepare_data(ocean_df)
            ocean_analyzer.train(X_train, y_train, X_test, y_test)
        else:
            print("Using pre-trained OCEAN model")

        # Test analysis with more diverse text samples
        test_texts = [
            "I absolutely love this new product! Best purchase ever!",
            "This is the worst experience ever. Never buying again.",
            "Just received my order and it isn't exactly what I wanted!",
            "I prefer spending time alone with a good book rather than going to parties.",
            "I always plan everything in advance and stick to my schedule."
        ]

        print("\nAnalyzing text samples...")
        results = ocean_analyzer.analyze(test_texts)

        # Print individual results
        print("\nIndividual Analysis Results:")
        for result in results:
            print(f"\nText: {result['text']}")
            print("OCEAN Traits:")
            for trait in ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']:
                if trait in result:
                    print(f"  {trait.capitalize()}: {result[trait]:.3f}")

        # Calculate and print average scores
        average_scores = ocean_analyzer.calculate_average_scores(results)
        print("\n\nAverage OCEAN Scores:")
        for trait, score in average_scores.items():
            print(f"  {trait.capitalize()}: {score:.3f}")

        # Generate personality summary
        print("\n" + "=" * 50)
        print("PERSONALITY PROFILE SUMMARY")
        print("=" * 50)
        summary = ocean_analyzer.generate_personality_summary(results)
        print(summary)
        print("=" * 50)

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    download_nltk_resources()
    main()