from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
import re
import random
from typing import List, Optional, Dict, Any


class TwitterScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        """
        Initialize the scraper with Chrome options

        Args:
            headless (bool): Whether to run Chrome in headless mode (default: True)
        """
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Add maximized option for better visibility in interactive mode
        if not headless:
            options.add_argument("--start-maximized")

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 15)

        # Store previously seen tweet IDs to avoid duplicates
        self.seen_tweets = set()

    def extract_username_from_url(self, url: str) -> str:
        """
        Extract username from Twitter/X profile URL

        Args:
            url (str): Twitter profile URL

        Returns:
            str: Extracted username
        """
        # Handle both twitter.com and x.com
        match = re.search(r'(?:https?:\/\/)?(?:www\.)?(?:twitter\.com|x\.com)\/([^\/?\s]+)', url)
        if match:
            return match.group(1).split('?')[0]  # Remove any query parameters
        return url  # If no match, return as-is (might be just a username)

    def get_profile_url(self, identifier: str, is_url: bool) -> str:
        """
        Return proper Twitter profile URL based on input type

        Args:
            identifier (str): Username or URL
            is_url (bool): Whether the identifier is a URL

        Returns:
            str: Formatted Twitter profile URL
        """
        if is_url:
            # Clean the URL
            url = identifier.strip()

            # If it already has a protocol, normalize it
            if url.startswith('http://') or url.startswith('https://'):
                # Replace twitter.com with x.com for consistency (or vice versa)
                # Keep x.com since Twitter rebranded
                url = url.replace('twitter.com', 'x.com')
                return url

            # If it doesn't have a protocol but looks like a URL
            if url.startswith('x.com/') or url.startswith('twitter.com/'):
                return f"https://{url.replace('twitter.com', 'x.com')}"

            # If it contains x.com or twitter.com somewhere
            if 'x.com/' in url or 'twitter.com/' in url:
                if not url.startswith('https://') and not url.startswith('http://'):
                    return f"https://{url.replace('twitter.com', 'x.com')}"
                return url.replace('twitter.com', 'x.com')

            # Fallback: extract username and build URL
            username = self.extract_username_from_url(identifier)
            return f"https://x.com/{username}"
        else:
            # It's just a username
            username = identifier.strip().lstrip('@')  # Remove @ if present
            return f"https://x.com/{username}"

    def get_tweet_id(self, tweet_element) -> str:
        """
        Generate a unique identifier for a tweet to avoid duplicates

        Args:
            tweet_element: The tweet DOM element

        Returns:
            str: A unique identifier for the tweet
        """
        try:
            # Try to get the actual tweet ID if possible
            tweet_link = tweet_element.find_element(By.XPATH, './/a[contains(@href, "/status/")]')
            href = tweet_link.get_attribute('href')
            if href:
                match = re.search(r'/status/(\d+)', href)
                if match:
                    return match.group(1)
        except (NoSuchElementException, StaleElementReferenceException):
            pass

        # Fallback: use the content text as identifier
        try:
            text_parts = tweet_element.find_elements(By.XPATH, './/div[@data-testid="tweetText"]')
            text = ' '.join([part.text for part in text_parts])
            if text:
                # Use first 50 chars as identifier if we can't get the actual ID
                return text[:50]
        except (NoSuchElementException, StaleElementReferenceException):
            pass

        # Last resort: use a random ID + timestamp
        return f"tweet_{time.time()}_{random.randint(1000, 9999)}"

    def perform_scroll(self, distance=None):
        """
        Perform a scrolling action with various strategies

        Args:
            distance (int, optional): Specific scroll distance. If None, scrolls to bottom.
        """
        if distance:
            self.driver.execute_script(f"window.scrollBy(0, {distance});")
        else:
            # Full scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Add a small random delay to mimic human behavior and give time for content to load
        time.sleep(1 + random.random())

    def scrape_tweets(self, identifier: str, is_url: bool, num_tweets: int, verbose: bool = False) -> Optional[
        List[str]]:
        """
        Scrape tweets from a user's profile with improved lazy loading handling

        Args:
            identifier (str): Username or URL
            is_url (bool): Whether the identifier is a URL
            num_tweets (int): Number of tweets to retrieve
            verbose (bool): Whether to print progress messages

        Returns:
            Optional[List[str]]: List of tweets if successful, None if profile is private
        """
        url = self.get_profile_url(identifier, is_url)
        if verbose:
            print(f"\nOpening Twitter profile: {url}")
        self.driver.get(url)

        # Initialize wait and scroll variables
        self.wait = WebDriverWait(self.driver, 15)

        try:
            # Check if profile is private
            private_element = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "These posts are protected")]'))
            )
            if private_element:
                if verbose:
                    print(f"Profile {identifier} is private.")
                return None
        except TimeoutException:
            pass  # Profile is not private

        tweets = []
        self.seen_tweets = set()  # Reset seen tweets set

        # Wait for initial tweets to load
        try:
            self.wait.until(EC.presence_of_element_located((By.XPATH, '//article[@data-testid="tweet"]')))
            if verbose:
                print("Initial tweets loaded successfully.")
        except TimeoutException:
            if verbose:
                print("No tweets found on profile or page loading issue.")
            return []

        # Scroll and collect variables
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        no_new_tweets_count = 0
        consecutive_failed_scrolls = 0
        max_no_new_tweets = 5  # Max number of scrolls without new tweets before trying alternative strategies
        max_consecutive_failures = 8  # Stop if we can't get new tweets after this many attempts
        max_scroll_attempts = 50  # Increased to ensure we get enough tweets
        scroll_count = 0

        if verbose:
            print(f"Target: {num_tweets} tweets")
            print("Starting to scroll and collect tweets...\n")

        # Main scroll and collect loop
        while len(tweets) < num_tweets and scroll_count < max_scroll_attempts:
            scroll_count += 1

            if verbose and scroll_count % 3 == 0:
                print(f"[Scroll {scroll_count}/{max_scroll_attempts}] Current count: {len(tweets)}/{num_tweets} tweets")

            # Find all visible tweet elements
            try:
                tweet_elements = self.driver.find_elements(By.XPATH, '//article[@data-testid="tweet"]')

                tweets_before = len(tweets)

                # Process any new tweets
                for tweet in tweet_elements:
                    try:
                        # Generate a unique ID for this tweet
                        tweet_id = self.get_tweet_id(tweet)

                        # Skip if we've already processed this tweet
                        if tweet_id in self.seen_tweets:
                            continue

                        # Mark as seen
                        self.seen_tweets.add(tweet_id)

                        # Get tweet text (handling multi-part tweets)
                        tweet_text_parts = tweet.find_elements(By.XPATH, './/div[@data-testid="tweetText"]')
                        full_text = ' '.join([part.text for part in tweet_text_parts])

                        if full_text:  # Only add if we got text
                            tweets.append(full_text)
                            if verbose:
                                print(f"✓ Collected tweet #{len(tweets)}: {full_text[:60]}...")

                            # Break if we've collected enough tweets
                            if len(tweets) >= num_tweets:
                                if verbose:
                                    print(f"\n✓ Target reached! Collected {len(tweets)} tweets.")
                                break
                    except (NoSuchElementException, StaleElementReferenceException):
                        continue
            except StaleElementReferenceException:
                # Page probably refreshed or structure changed, wait a moment
                if verbose:
                    print("⚠ Page structure changed, waiting...")
                time.sleep(1)
                continue

            # Check if we got any new tweets in this iteration
            new_tweets_count = len(tweets) - tweets_before

            if new_tweets_count == 0:
                no_new_tweets_count += 1
                consecutive_failed_scrolls += 1
                if verbose and consecutive_failed_scrolls % 3 == 0:
                    print(f"⚠ No new tweets found in last {consecutive_failed_scrolls} scrolls...")
            else:
                if verbose and new_tweets_count > 0:
                    print(f"✓ Found {new_tweets_count} new tweets in this scroll")
                no_new_tweets_count = 0  # Reset counter when we find new tweets
                consecutive_failed_scrolls = 0  # Reset consecutive failures

            # Break if we've collected enough tweets
            if len(tweets) >= num_tweets:
                break

            # Stop if we've failed too many times consecutively
            if consecutive_failed_scrolls >= max_consecutive_failures:
                if verbose:
                    print(
                        f"\n⚠ Stopping: No new tweets after {consecutive_failed_scrolls} consecutive scroll attempts.")
                    print(f"Collected {len(tweets)} tweets (requested: {num_tweets})")
                break

            # Try different scrolling strategies based on our success
            if no_new_tweets_count >= max_no_new_tweets:
                # Try a different scrolling strategy
                if verbose:
                    print("⟳ Trying alternative scrolling strategy...")

                # Strategy 1: Scroll to a random position
                page_height = self.driver.execute_script("return document.body.scrollHeight")
                random_position = random.randint(int(page_height * 0.3), int(page_height * 0.7))
                self.driver.execute_script(f"window.scrollTo(0, {random_position});")
                time.sleep(1.5)

                # Strategy 2: Scroll back up a bit, then down again (helps trigger lazy loading)
                self.driver.execute_script("window.scrollBy(0, -300);")
                time.sleep(0.5)
                self.driver.execute_script("window.scrollBy(0, 600);")
                time.sleep(1)

                # Strategy 3: Try clicking "Show more" buttons if they exist
                try:
                    show_more_buttons = self.driver.find_elements(By.XPATH, '//div[contains(text(), "Show more")]')
                    if show_more_buttons:
                        for button in show_more_buttons[:2]:
                            try:
                                button.click()
                                time.sleep(0.8)
                            except:
                                pass
                except:
                    pass

                no_new_tweets_count = 0  # Reset counter after trying alternative method
            else:
                # Regular scrolling strategy - scroll to bottom
                self.perform_scroll()  # Scroll to bottom

                # Wait for new content to load
                time.sleep(1.5 + random.random() * 0.5)

            # Check if we've reached the end of the page
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Page height hasn't changed, try a smaller incremental scroll
                self.driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(1)
            last_height = new_height

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"Scraping complete!")
            print(f"Collected: {len(tweets)}/{num_tweets} tweets")
            print(f"Total scrolls: {scroll_count}")
            print(f"{'=' * 60}\n")

        return tweets[:num_tweets]  # Return only the requested number of tweets

    def scrape_profile_info(self, identifier: str, is_url: bool) -> Optional[Dict[str, Any]]:
        """
        Scrape basic profile information

        Args:
            identifier (str): Username or URL
            is_url (bool): Whether the identifier is a URL

        Returns:
            Optional[Dict[str, Any]]: Profile information if successful, None if profile not found
        """
        url = self.get_profile_url(identifier, is_url)
        self.driver.get(url)

        try:
            # Wait for profile to load
            self.wait.until(EC.presence_of_element_located((By.XPATH, '//div[@data-testid="primaryColumn"]')))

            # Initialize profile data dictionary
            profile_data = {
                'username': self.extract_username_from_url(identifier) if is_url else identifier.strip().lstrip('@'),
                'display_name': '',
                'bio': '',
                'location': '',
                'website': '',
                'join_date': '',
                'following_count': '',
                'followers_count': '',
                'is_private': False
            }

            # Check if profile is private
            try:
                private_element = self.driver.find_element(By.XPATH,
                                                           '//span[contains(text(), "These posts are protected")]')
                if private_element:
                    profile_data['is_private'] = True
            except NoSuchElementException:
                pass

            # Get display name
            try:
                display_name = self.driver.find_element(By.XPATH,
                                                        '//div[@data-testid="primaryColumn"]//span[contains(@class, "fullname")]')
                profile_data['display_name'] = display_name.text
            except NoSuchElementException:
                pass

            # Get bio
            try:
                bio = self.driver.find_element(By.XPATH, '//div[contains(@data-testid, "UserDescription")]')
                profile_data['bio'] = bio.text
            except NoSuchElementException:
                pass

            # Get follower and following counts
            try:
                following = self.driver.find_element(By.XPATH, '//a[contains(@href, "/following")]/span')
                profile_data['following_count'] = following.text
            except NoSuchElementException:
                pass

            try:
                followers = self.driver.find_element(By.XPATH, '//a[contains(@href, "/followers")]/span')
                profile_data['followers_count'] = followers.text
            except NoSuchElementException:
                pass

            return profile_data

        except TimeoutException:
            return None
        except Exception as e:
            print(f"Error scraping profile info: {e}")
            return None

    def close(self, delay: int = 0):
        """
        Close the browser

        Args:
            delay (int): Delay in seconds before closing (useful for interactive mode)
        """
        if delay > 0:
            time.sleep(delay)
        self.driver.quit()


def get_user_input():
    """
    Interactive command-line interface for the scraper

    Returns:
        tuple: (identifier, is_url, num_tweets)
    """
    print("\n" + "=" * 50)
    print("TWITTER TWEET SCRAPER".center(50))
    print("=" * 50)
    print("\nThis script will open a Chrome window to scrape tweets.")
    print("You'll see the browser automatically scroll through the profile.\n")

    while True:
        print("\nChoose search method:")
        print("1. Username")
        print("2. Profile URL (e.g., 'https://x.com/username')")
        choice = input("Enter 1 or 2: ").strip()

        if choice == '1':
            identifier = input("\nEnter Twitter username (without @): ").strip()
            if not identifier:
                print("Username cannot be empty!")
                continue
            if any(c in identifier for c in ['/', ':', ' ']):
                print("Invalid username! Don't include slashes, spaces or URLs")
                continue
            is_url = False
            break

        elif choice == '2':
            url = input("\nEnter full Twitter profile URL: ").strip()
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            if 'x.com/' not in url and 'twitter.com/' not in url:
                print("Please enter a valid Twitter/X URL (e.g., https://x.com/username)")
                continue
            identifier = url
            is_url = True
            break

        else:
            print("Invalid choice. Please enter 1 or 2")

    while True:
        try:
            num_tweets = int(input("\nNumber of tweets to retrieve (1-100): ") or "10")
            if 1 <= num_tweets <= 100:
                break
            print("Please enter a number between 1 and 100")
        except ValueError:
            print("Please enter a valid number")

    return identifier, is_url, num_tweets


def main():
    """
    Main function for command-line usage
    """
    print("\nStarting Twitter Scraper...")
    identifier, is_url, num_tweets = get_user_input()

    print("\nLaunching Chrome browser...")
    scraper = TwitterScraper(headless=False)  # Show browser for interactive mode

    try:
        print("\nScraping in progress - watch the browser window...")
        tweets = scraper.scrape_tweets(identifier, is_url, num_tweets, verbose=True)

        if tweets is not None:
            username = identifier if not is_url else scraper.extract_username_from_url(identifier)
            print("\n" + "=" * 50)
            print(f"SCRAPED {len(tweets)} TWEETS FROM @{username}".center(50))
            print("=" * 50)
            for i, tweet in enumerate(tweets, 1):
                print(f"\nTweet {i}:\n{tweet}\n")
        else:
            print("\nFailed to scrape tweets (private profile or other error)")
    except Exception as e:
        print(f"\nError occurred: {e}")
    finally:
        scraper.close(delay=5)  # Close browser after 5 seconds
    print("\nScript finished.")


if __name__ == "__main__":
    main()