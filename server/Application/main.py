import datetime
import json
import os
import re
import traceback

import pyodbc
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, InternalServerError, Conflict, Unauthorized, NotFound
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from Core.OCEANAnalyzer import OceanAnalyzer, download_nltk_resources
from Core.TextPreProcessor import TextPreprocessor
from Core.TweetScraper import TwitterScraper
from Operation.User import User
from Operation.Analysis import Analysis


class PersonaInsight:
    """Main class for the PersonaInsight API application"""

    def __init__(self, jwt_secret_key='PersonaInsight', jwt_expires=datetime.timedelta(hours=1)):

        self.app = Flask(__name__)

        CORS(self.app, resources={
            r"/*": {
                "origins": ["http://localhost:3000"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"]
            }
        })

        # Configure JWT
        self.app.config['JWT_SECRET_KEY'] = jwt_secret_key
        self.app.config['JWT_ACCESS_TOKEN_EXPIRES'] = jwt_expires
        self.app.config['JWT_TOKEN_LOCATION'] = ['headers']
        self.app.config['JWT_HEADER_NAME'] = 'Authorization'
        self.app.config['JWT_HEADER_TYPE'] = 'Bearer'
        self.jwt = JWTManager(self.app)

        # Database configuration
        self.server = 'LATITUDE-7490'
        self.database = 'PersonaInsight'
        self.db_username = r'LATITUDE-7490\Owais'
        self.trusted_connection = True

        # Analysis components
        self.preprocessor = None
        self.ocean_analyzer = None

        # Register routes
        self._register_routes()

        # Register error handlers
        self._register_error_handlers()

        # Add before_request handler for model initialization
        self.app.before_request(self.initialize_models)

        self.token_blacklist = set()

        # Add JWT callbacks
        self._register_jwt_callbacks()

    def initialize_models(self):
        """Initialize the OCEAN analyzer before handling the first request."""
        # Skip initialization for static resources
        if request.path.startswith('/static'):
            return

        # Only initialize if not already done
        if self.preprocessor is None or self.ocean_analyzer is None:
            # Download NLTK resources
            download_nltk_resources()

            # Initialize the text preprocessor
            self.preprocessor = TextPreprocessor()

            # Initialize the OCEAN analyzer
            self.ocean_analyzer = OceanAnalyzer(self.preprocessor)

            # Try to load existing model first
            model_loaded = self.ocean_analyzer.load_model()

            if not model_loaded:
                print("OCEAN model not found. Training new model...")
                ocean_df = self.ocean_analyzer.load_data('mypersonality_final.csv')
                X_train, X_test, y_train, y_test = self.ocean_analyzer.prepare_data(ocean_df)
                self.ocean_analyzer.train(X_train, y_train, X_test, y_test)
            else:
                print("Using pre-trained OCEAN model")

    def _register_routes(self):
        """Register all API routes with the Flask app"""
        # Route definitions
        routes = [
            ('/', ['GET'], self.index),
            ('/analyze', ['POST'], self.analyze_tweets),
            ('/api/add_user', ['POST'], self.add_user),
            ('/api/users/login', ['POST'], self.login_user),
            ('/api/update_users', ['PUT'], self.update_user, True),  # JWT protected
            ('/api/delete_user', ['DELETE'], self.delete_user, True),  # JWT protected
            ('/api/check_token', ['GET'], self.check_token, True),  # JWT protected
            ('/api/tweets/username/<username>', ['GET'], self.get_tweets_by_username),
            ('/api/tweet'
             's/url', ['GET'], self.get_tweets_by_url),
            ('/api/analyze_profile', ['GET'], self.analyze_profile),
            ('/api/profile_info', ['GET'], self.get_profile_info),
            ('/api/logout', ['GET'], self.logout_user, True),
            ('/api/get_analysis_by_email', ['GET'], self.get_user_analyses)
        ]

        # Register each route
        for route_info in routes:
            if len(route_info) == 3:
                route, methods, handler = route_info
                self.app.route(route, methods=methods)(handler)
            elif len(route_info) == 4:
                route, methods, handler, jwt_protected = route_info
                if jwt_protected:
                    self.app.route(route, methods=methods)(jwt_required()(handler))

    def _register_error_handlers(self):
        """Register error handlers for different error types"""
        self.app.errorhandler(BadRequest)(self.handle_bad_request)
        self.app.errorhandler(Unauthorized)(self.handle_unauthorized)
        self.app.errorhandler(NotFound)(self.handle_not_found)
        self.app.errorhandler(Conflict)(self.handle_conflict)
        self.app.errorhandler(InternalServerError)(self.handle_internal_server_error)
        self.app.errorhandler(Exception)(self.handle_unexpected_error)

    def debug_request(self):
        """Log request details for debugging"""
        print("\n=== DEBUG REQUEST INFO ===")
        print(f"Method: {request.method}")
        print(f"Path: {request.path}")
        print("Headers:")
        for key, value in request.headers.items():
            if key.lower() == 'authorization':
                print(f"  {key}: Bearer [REDACTED]")  # Don't log full token
            else:
                print(f"  {key}: {value}")

        print("Body:")
        if request.is_json:
            body = request.get_json()
            # Redact password if present
            if isinstance(body, dict):
                body_copy = body.copy()
                if 'password' in body_copy:
                    body_copy['password'] = '[REDACTED]'
                if 'current_password' in body_copy:
                    body_copy['current_password'] = '[REDACTED]'
                if 'new_password' in body_copy:
                    body_copy['new_password'] = '[REDACTED]'
                print(json.dumps(body_copy, indent=2))
        else:
            print("[Not JSON]")
        print("=========================\n")

    def parameters_checker(self, required_fields, data):
        """Check for missing fields in the provided data."""
        return [field for field in required_fields if field not in data]

    def parse_personality_summary(self, summary_text):
        """
        Parse the personality summary text into structured components.

        Args:
            summary_text (str): The raw personality summary text

        Returns:
            dict: A structured dictionary with categorized insights
        """
        structured_summary = {
            "GENERAL_INSIGHTS": [],
            "ADDITIONAL_INSIGHTS": [],
            "RELATIONSHIP_INSIGHTS": [],
            "WORK_INSIGHTS": []
        }

        # Define patterns to identify different sections
        section_patterns = {
            "GENERAL_INSIGHTS": r"Based on the analyzed text, this personality profile reveals someone who:(.*?)(?=\n\nAdditional insights:|$)",
            "ADDITIONAL_INSIGHTS": r"Additional insights:(.*?)(?=\n\nIn relationships|$)",
            "RELATIONSHIP_INSIGHTS": r"In relationships, this person likely:(.*?)(?=\n\nIn work environments|$)",
            "WORK_INSIGHTS": r"In work environments, this person typically:(.*?)(?=\n\nNote:|$)"
        }

        # Extract and clean insights for each section
        for section, pattern in section_patterns.items():
            match = re.search(pattern, summary_text, re.DOTALL)
            if match:
                # Extract bullet points and clean them
                bullet_points = re.findall(r'•\s+(.*?)(?=\n|$)', match.group(1))
                structured_summary[section] = [point.strip() for point in bullet_points if point.strip()]

        return structured_summary

    # Route handler methods
    def index(self):
        """Root endpoint handler"""
        return "PersonaInsight and Twitter Scraper Server Up & Running"

    def analyze_tweets(self):
        """
        API route to analyze provided tweets
        """
        try:
            # Get JSON data from request
            data = request.get_json()

            # Check if tweets array exists
            if not data or 'tweets' not in data or not isinstance(data['tweets'], list):
                return jsonify({
                    'error': 'Invalid request. Expected JSON with "tweets" array.'
                }), 400

            tweets = data['tweets']

            # Check if tweets array is empty
            if not tweets:
                return jsonify({
                    'error': 'No tweets provided for analysis.'
                }), 400

            # Preprocess tweets
            preprocessed_tweets = [self.preprocessor.preprocess_text(tweet) for tweet in tweets]

            # Analyze tweets
            results = self.ocean_analyzer.analyze(preprocessed_tweets)

            # Calculate average scores
            average_scores = self.ocean_analyzer.calculate_average_scores(results)

            # Generate personality summary
            personality_summary_text = self.ocean_analyzer.generate_personality_summary(results)

            # Parse and structure the summary text into components
            structured_summary = self.parse_personality_summary(personality_summary_text)

            # Prepare response
            response = {
                'individual_results': results,
                'average_scores': average_scores,
                'summary': structured_summary
            }

            return jsonify(response), 200

        except Exception as e:
            return jsonify({
                'error': f'An error occurred during analysis: {str(e)}'
            }), 500

    def add_user(self):
        """Create a new user account"""
        self.debug_request()
        try:
            data = request.get_json()
            if not data:
                raise BadRequest("No JSON data provided")

            missing_fields = self.parameters_checker(
                required_fields=['full_name', 'email', 'password'],
                data=data
            )
            if missing_fields:
                raise BadRequest(f'Missing required fields: {", ".join(missing_fields)}')

            # Validate email format
            if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
                raise BadRequest("Invalid email format")

            # Validate password strength (basic example)
            if len(data['password']) < 8:
                raise BadRequest("Password must be at least 8 characters long")

            user = User(
                full_name=data['full_name'],
                email=data['email'],
                password=data['password']
            )

            # Establish connection
            user.get_connection(
                server=self.server,
                database=self.database,
                trusted_connection=self.trusted_connection
            )

            # Add user to database
            user_id = user.add_user()

            return jsonify({
                'id': user_id,
                'message': 'User registered successfully',
                'success': True
            }), 201

        except ValueError as e:
            raise BadRequest(str(e))
        except pyodbc.Error as e:
            raise InternalServerError(f"Database error: {str(e)}")
        except Exception as e:
            raise InternalServerError(f"Unexpected error: {str(e)}")

    def login_user(self):
        """Authenticate a user and return JWT token"""
        self.debug_request()
        try:
            data = request.get_json()
            if not data:
                raise BadRequest("No JSON data provided")

            missing_fields = self.parameters_checker(
                required_fields=['email', 'password'],
                data=data
            )
            if missing_fields:
                raise BadRequest(f'Missing required fields: {", ".join(missing_fields)}')

            user = User()
            user.get_connection(
                server=self.server,
                database=self.database,
                trusted_connection=self.trusted_connection
            )

            result = user.get_user(data['email'], data['password'])

            if isinstance(result, str):
                if result == "User not found":
                    raise NotFound("User not found")
                elif result == "Invalid password":
                    raise Unauthorized("Invalid password")
                else:
                    raise InternalServerError("Unexpected response from server")

            # Create JWT token with user ID as identity
            # Convert ID to string to ensure compatibility
            user_id = str(result['ID'])
            access_token = create_access_token(identity=user_id)

            # Debug token creation
            print(f"Created token for user ID: {user_id}")

            # Remove password before returning user data
            if 'PASSWORD' in result:
                del result['PASSWORD']

            return jsonify({
                'user': result,
                'access_token': access_token,
                'message': 'Login successful',
                'success': True
            }), 200

        except BadRequest as e:
            raise
        except NotFound as e:
            raise
        except Unauthorized as e:
            raise
        except pyodbc.Error as e:
            raise InternalServerError(f"Database error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error in login: {str(e)}")
            print(traceback.format_exc())
            raise InternalServerError(f"Unexpected error: {str(e)}")

    def update_user(self):
        """Update user information (JWT protected)"""
        self.debug_request()
        try:
            # Get current user ID from JWT
            current_user_id = get_jwt_identity()

            # Convert string ID to int if needed
            user_id = int(current_user_id) if current_user_id.isdigit() else current_user_id

            # Debug info
            print(f"Authenticated user ID: {user_id}")

            data = request.get_json()
            print(data)
            if not data:
                raise BadRequest("No JSON data provided")

            # Check required fields
            missing_fields = self.parameters_checker(
                required_fields=['full_name', 'email', 'current_password'],
                data=data
            )
            if missing_fields:
                raise BadRequest(f'Missing required fields: {", ".join(missing_fields)}')

            user = User()
            user.get_connection(
                server=self.server,
                database=self.database,
                trusted_connection=self.trusted_connection
            )

            # Get new_password if provided
            new_password = data.get('new_password')

            # Update the user
            result = user.update_user(
                user_id=user_id,
                full_name=data['full_name'],
                email=data['email'],
                curr_password=data['current_password'],
                new_password=new_password
            )

            if result == "User not found":
                raise NotFound("User not found")
            elif result == "Invalid password":
                raise Unauthorized("Invalid password")
            elif result == "Email already exists for another user":
                raise Conflict("Email already exists for another user")

            return jsonify({
                'message': result,
                'success': True
            }), 200

        except (BadRequest, NotFound, Unauthorized, Conflict) as e:
            raise
        except pyodbc.Error as e:
            print(f"Database error in update_user: {str(e)}")
            raise InternalServerError(f"Database error: {str(e)}")
        except Exception as e:
            # Print the exception for debugging
            print(f"Error in update_user: {str(e)}")
            print(traceback.format_exc())
            raise InternalServerError(f"Unexpected error: {str(e)}")

    def delete_user(self):
        """Delete a user account (JWT protected)"""
        self.debug_request()
        try:
            # Get current user ID from JWT
            current_user_id = get_jwt_identity()

            # Convert string ID to int if needed
            user_id = int(current_user_id) if current_user_id.isdigit() else current_user_id

            print(f"Delete request for user ID: {user_id}")

            data = request.get_json()
            if not data:
                raise BadRequest("No JSON data provided")

            missing_fields = self.parameters_checker(
                required_fields=['email', 'password'],
                data=data
            )
            if missing_fields:
                raise BadRequest(f'Missing required fields: {", ".join(missing_fields)}')

            user = User()
            user.get_connection(
                server=self.server,
                database=self.database,
                trusted_connection=self.trusted_connection
            )

            result = user.delete_user(
                user_id=user_id,
                email=data['email'],
                password=data['password']
            )

            if not result:
                raise NotFound("User not found or credentials incorrect")

            return jsonify({
                'message': 'User deleted successfully',
                'success': True
            }), 200

        except (BadRequest, NotFound, Unauthorized) as e:
            raise
        except pyodbc.Error as e:
            raise InternalServerError(f"Database error: {str(e)}")
        except Exception as e:
            print(f"Error in delete_user: {str(e)}")
            print(traceback.format_exc())
            raise InternalServerError(f"Unexpected error: {str(e)}")

    @jwt_required()
    def logout_user(self):
        """Logout user by blacklisting token"""
        try:
            jti = get_jwt()["jti"]  # Get unique identifier for the token
            self.token_blacklist.add(jti)

            # Debug logging
            print(f"Token blacklisted - JTI: {jti}")

            return jsonify({
                'message': 'Successfully logged out',
                'success': True
            }), 200

        except Exception as e:
            print(f"Logout error: {str(e)}")
            raise InternalServerError("Failed to process logout request")

    def check_token(self):
        """Endpoint to verify JWT token is working correctly"""
        try:
            current_user_id = get_jwt_identity()
            # Get the full JWT claims
            jwt_claims = get_jwt()

            # Convert string ID to int if needed for database query
            user_id = int(current_user_id) if current_user_id.isdigit() else current_user_id

            # Verify user exists in database
            user = User()
            user.get_connection(
                server=self.server,
                database=self.database,
                trusted_connection=self.trusted_connection
            )

            # Get user info from database
            user_info = user.get_user_by_id(user_id)

            if isinstance(user_info, str) and user_info == "User not found":
                raise NotFound("User not found")

            # Remove password from response
            if 'PASSWORD' in user_info:
                del user_info['PASSWORD']

            return jsonify({
                'message': 'Token is valid',
                'user_id': current_user_id,
                'user_info': user_info,
                'token_exp': jwt_claims.get('exp'),
                'success': True
            }), 200

        except Exception as e:
            print(f"Error in check_token: {str(e)}")
            print(traceback.format_exc())
            raise InternalServerError(f"Error verifying token: {str(e)}")

    def get_tweets_by_username(self, username):
        """
        API route to get tweets by username
        Example: /api/tweets/username/twitter?count=10
        """
        try:
            # Get query parameters
            count = request.args.get('count', default=10, type=int)

            # Validate parameters
            if not username:
                return jsonify({"error": "Username cannot be empty"}), 400

            if count <= 0 or count > 100:
                return jsonify({"error": "Count must be between 1 and 100"}), 400

            # Initialize scraper
            scraper = TwitterScraper(headless=False)

            try:
                # Scrape tweets
                tweets = scraper.scrape_tweets(username, is_url=False, num_tweets=count)

                if tweets is None:
                    return jsonify({
                        "error": "Cannot access tweets",
                        "message": "Profile is private or does not exist"
                    }), 403

                return jsonify({
                    "username": username,
                    "count": len(tweets),
                    "tweets": tweets
                })

            finally:
                scraper.close()

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def get_tweets_by_url(self):
        """
        API route to get tweets by URL
        Example: /api/tweets/url?url=https://twitter.com/username&count=10
        """
        try:
            # Get query parameters
            url = request.args.get('url', default=None, type=str)
            count = request.args.get('count', default=10, type=int)

            # Validate parameters
            if not url:
                return jsonify({"error": "URL parameter is required"}), 400

            if 'twitter.com' not in url and 'x.com' not in url:
                return jsonify({"error": "Invalid Twitter URL"}), 400

            if count <= 0 or count > 100:
                return jsonify({"error": "Count must be between 1 and 100"}), 400

            # Initialize scraper
            scraper = TwitterScraper(headless=False)

            try:
                # Extract username from URL for response
                username = scraper.extract_username_from_url(url)

                # Scrape tweets
                tweets = scraper.scrape_tweets(url, is_url=True, num_tweets=count)

                if tweets is None:
                    return jsonify({
                        "error": "Cannot access tweets",
                        "message": "Profile is private or does not exist"
                    }), 403

                return jsonify({
                    "username": username,
                    "url": url,
                    "count": len(tweets),
                    "tweets": tweets
                })

            finally:
                scraper.close()

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def str_to_bool(self, value):
        """
        Convert string to boolean safely

        Args:
            value: String value to convert

        Returns:
            bool: True if value is 'true', '1', 'yes' (case insensitive), False otherwise
        """
        if value is None:
            return False
        return str(value).lower() == 'true'

    def analyze_profile(self):
        """
        Combined endpoint that scrapes tweets, performs personality analysis, and saves results to database
        Example: /api/analyze_profile?username=twitter&count=20&email=user@example.com
        """
        try:
            # Get query parameters
            username = request.args.get('username', default=None, type=str)
            url = request.args.get('url', default=None, type=str)
            count = request.args.get('count', default=10, type=int)
            email = request.args.get('email', default=None, type=str)

            # FIXED: Properly parse boolean parameter using helper method
            realtime_processing = self.str_to_bool(request.args.get('realtimeProcessing', 'false'))

            # Validate parameters

            if url and 'twitter.com' not in url and 'x.com' not in url:
                return jsonify({"error": "Invalid Twitter URL"}), 400

            if count <= 0 or count > 100:
                return jsonify({"error": "Count must be between 1 and 100"}), 400

            if not username and not url:
                return jsonify({"error": "Either username or url parameter is required"}), 400

            if url and 'twitter.com' not in url and 'x.com' not in url:
                return jsonify({"error": "Invalid Twitter URL"}), 400

            if count <= 0 or count > 100:
                return jsonify({"error": "Count must be between 1 and 100"}), 400

            # Determine if we're using URL or username
            is_url = url is not None
            identifier = url if is_url else username

            # Initialize scraper
            scraper = TwitterScraper(headless=not realtime_processing)

            try:
                # Scrape tweets
                tweets = scraper.scrape_tweets(identifier, is_url=is_url, num_tweets=count)

                if tweets is None:
                    return jsonify({
                        "error": "Cannot access tweets",
                        "message": "Profile is private or does not exist"
                    }), 403

                # Get username for response
                profile_username = username if not is_url else scraper.extract_username_from_url(url)

                # Preprocess tweets
                preprocessed_tweets = [self.preprocessor.preprocess_text(tweet) for tweet in tweets]

                # Analyze tweets
                results = self.ocean_analyzer.analyze(preprocessed_tweets)

                # Calculate average scores
                average_scores = self.ocean_analyzer.calculate_average_scores(results)

                # Generate personality summary
                personality_summary_text = self.ocean_analyzer.generate_personality_summary(results)

                # Parse and structure the summary text into components
                structured_summary = self.parse_personality_summary(personality_summary_text)

                # Prepare response
                response = {
                    'username': profile_username,
                    'tweets_analyzed': len(tweets),
                    'tweets': tweets,
                    'individual_results': results,
                    'average_scores': average_scores,
                    'summary': structured_summary
                }

                # Save to database only if email is provided and analysis was successful
                if email:
                    try:
                        analysis = Analysis(
                            email=email,
                            username=profile_username,
                            tweets_count=len(tweets),
                            average_scores=average_scores
                        )

                        # Convert insights into properly formatted list for Analysis class
                        insights = []
                        for insight_type, insight_list in structured_summary.items():
                            if insight_list:  # Only add if there are insights for this type
                                insights.append({
                                    'type': insight_type,  # Keep original camelCase for consistency
                                    'text': ", ".join(insight_list)
                                })

                        # Set insights to the analysis object
                        analysis.insights = insights

                        # Get database connection parameters from the current instance
                        analysis.get_connection(
                            server=self.server,
                            database=self.database,
                            trusted_connection=self.trusted_connection
                        )

                        # Save the analysis
                        analysis_id = analysis.add_analysis()
                        response['analysis_id'] = analysis_id
                        response['saved_to_db'] = True
                    except Exception as db_error:
                        # Log the database error but don't fail the request
                        print(f"Failed to save analysis to database: {str(db_error)}")
                        print(traceback.format_exc())
                        response['saved_to_db'] = False
                        response['db_error'] = str(db_error)
                else:
                    response['saved_to_db'] = False
                    response['message'] = "Analysis not saved to database (no email provided)"

                return jsonify(response), 200

            finally:
                scraper.close()

        except Exception as e:
            # Don't attempt to save anything if there was an error in analysis
            print(f"Error in analyze_profile: {str(e)}")
            print(traceback.format_exc())
            return jsonify({"error": str(e)}), 500

    @jwt_required()
    def get_user_analyses(self):
        """
        API endpoint to retrieve all analyses for the authenticated user

        Returns:
            JSON response containing:
            - analyses: List of analysis records with insights
            - success: Boolean indicating success
            - error: Error message if any (None if successful)
        """
        try:
            # Get the current user's email from JWT
            current_user_email = request.args.get('email', default=None, type=str)

            # Debug logging
            print(f"Fetching analyses for user: {current_user_email}")

            # Get analyses using the Analysis class
            analysis = Analysis()
            analysis.get_connection(
                server=self.server,
                database=self.database,
                trusted_connection=self.trusted_connection
            )

            analyses = analysis.get_analyses_by_user(current_user_email)

            # Format the response
            response = {
                'analyses': analyses,
                'success': True,
                'error': None,
                'count': len(analyses)
            }

            return jsonify(response), 200

        except ValueError as e:
            return jsonify({
                'analyses': [],
                'success': False,
                'error': str(e),
                'count': 0
            }), 400

        except pyodbc.Error as e:
            return jsonify({
                'analyses': [],
                'success': False,
                'error': f"Database error: {str(e)}",
                'count': 0
            }), 500

        except Exception as e:
            return jsonify({
                'analyses': [],
                'success': False,
                'error': f"Unexpected error: {str(e)}",
                'count': 0
            }), 500

    def get_profile_info(self):
        """
        Endpoint to fetch basic profile information
        Example: /api/profile_info?username=twitter
        """
        try:
            # Get query parameters
            username = request.args.get('username', default=None, type=str)
            url = request.args.get('url', default=None, type=str)

            # Validate parameters
            if not username and not url:
                return jsonify({"error": "Either username or url parameter is required"}), 400

            if url and 'twitter.com' not in url and 'x.com' not in url:
                return jsonify({"error": "Invalid Twitter URL"}), 400

            # Determine if we're using URL or username
            is_url = url is not None
            identifier = url if is_url else username

            # Initialize scraper
            scraper = TwitterScraper(headless=False)

            try:
                # Scrape profile info
                profile_info = scraper.scrape_profile_info(identifier, is_url=is_url)

                if profile_info is None:
                    return jsonify({
                        "error": "Cannot access profile",
                        "message": "Profile does not exist or is unavailable"
                    }), 404

                return jsonify(profile_info), 200

            finally:
                scraper.close()

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Error handlers
    def handle_bad_request(self, e):
        return jsonify({
            'message': str(e),
            'success': False
        }), 400

    def handle_unauthorized(self, e):
        return jsonify({
            'message': str(e),
            'success': False
        }), 401

    def handle_not_found(self, e):
        return jsonify({
            'message': str(e),
            'success': False
        }), 404

    def handle_conflict(self, e):
        return jsonify({
            'message': str(e),
            'success': False
        }), 409

    def _register_jwt_callbacks(self):
        """Register JWT callbacks for token verification"""

        @self.jwt.token_in_blocklist_loader
        def check_if_token_revoked(jwt_header, jwt_payload):
            jti = jwt_payload["jti"]
            return jti in self.token_blacklist

    def handle_internal_server_error(self, e):
        return jsonify({
            'message': str(e),
            'success': False
        }), 500

    def handle_unexpected_error(self, e):
        print(f"Unexpected error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'message': "An unexpected error occurred",
            'success': False
        }), 500

    def run(self, host='0.0.0.0', port=5000, debug=True):
        """Run the Flask application"""
        self.app.run(host=host, port=port, debug=debug)


# Main entry point
if __name__ == '__main__':
    # Create the PersonaInsight application
    app = PersonaInsight()

    # Run the application
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)