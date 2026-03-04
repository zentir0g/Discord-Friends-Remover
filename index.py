import os
import sys
import json
import time
import threading
import random
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style
import tls_client

init(autoreset=True)

# Global lock for thread-safe printing
print_lock = threading.Lock()

def setTitle(title: str = None):
    """Set console title"""
    os.system(f"title {title}" if os.name == "nt" else f"echo -ne '\033]0;{title}\007'")

def clear():
    """Clear the console"""
    os.system("cls" if os.name == "nt" else "clear")

def safe_print(text, color=Fore.WHITE):
    """Thread-safe printing with color"""
    with print_lock:
        print(color + text + Style.RESET_ALL)

# Logo
logo = """
__________             __  .__                      
\____    /____   _____/  |_|__|______  ____   ____  
  /     // __ \ /    \   __\  \_  __ \/  _ \ / ___\ 
 /     /\  ___/|   |  \  |  |  ||  | \(  <_> ) /_/  >
/_______ \___  >___|  /__| |__||__|   \____/\___  / 
        \/   \/     \/                     /_____/  
               discord.gg/zentirog
"""

class DiscordFriendRemover:
    def __init__(self, token):
        self.token = token
        self.session = self._create_session()
        self.base_headers = self._get_base_headers()
        self.friends_file = "users.txt"
        self.blacklist_file = "blacklist.txt"
        
    def _create_session(self):
        """Create a TLS client session with browser-like fingerprint"""
        try:
            session = tls_client.Session(
                client_identifier="chrome_120",
                random_tls_extension_order=True
            )
            return session
        except Exception as e:
            safe_print(f"[✗] Error creating session: {e}", Fore.RED)
            return None
    
    def _get_base_headers(self):
        """Return base headers for Discord API requests"""
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": self.token,
            "origin": "https://discord.com",
            "priority": "u=1, i",
            "referer": "https://discord.com/channels/@me",
            "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "x-discord-locale": "en-US",
            "x-discord-timezone": "America/New_York",
            "x-debug-options": "bugReporterEnabled",
            "x-super-properties": self._get_super_properties()
        }
    
    def _get_super_properties(self):
        """Generate super properties for browser fingerprinting"""
        properties = {
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "browser_version": "121.0.0.0",
            "os_version": "10",
            "referrer": "https://discord.com",
            "referring_domain": "discord.com",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": 253389,
            "client_event_source": None
        }
        return base64.b64encode(json.dumps(properties).encode()).decode()
    
    def get_friends(self):
        """Fetch all friends from Discord API"""
        print(Fore.YELLOW + "\n[*] Fetching friends list...")
        url = "https://discord.com/api/v9/users/@me/relationships"
        
        try:
            response = self.session.get(url, headers=self.base_headers)
            
            if response.status_code == 200:
                friends = response.json()
                user_ids = []
                
                for friend in friends:
                    if 'user' in friend and 'id' in friend['user']:
                        user_id = friend['user']['id']
                        username = friend['user'].get('username', 'Unknown')
                        user_ids.append(user_id)
                        print(Fore.CYAN + f"[+] Found: {username} ({user_id})")
                
                # Save all user IDs to file
                with open(self.friends_file, 'w') as f:
                    for user_id in user_ids:
                        f.write(f"{user_id}\n")
                
                print(Fore.GREEN + f"\n[✓] Successfully saved {len(user_ids)} friends to {self.friends_file}")
                return user_ids
            else:
                print(Fore.RED + f"\n[✗] Failed to fetch friends. Status: {response.status_code}")
                if response.text:
                    print(Fore.RED + f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(Fore.RED + f"\n[✗] Error fetching friends: {e}")
            return None
    
    def remove_friend(self, user_id):
        """Remove a friend by user ID"""
        url = f"https://discord.com/api/v9/users/@me/relationships/{user_id}"
        
        headers = self.base_headers.copy()
        headers["x-context-properties"] = "eyJsb2NhdGlvbiI6IkZyaWVuZHMifQ=="
        
        try:
            response = self.session.delete(url, headers=headers)
            
            if response.status_code == 204:
                return True, None
            elif response.status_code == 429:
                retry_after = response.json().get('retry_after', 1)
                return False, f"Rate limited (wait {retry_after}s)"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, str(e)
    
    def load_user_ids(self):
        """Load user IDs from file"""
        if not os.path.exists(self.friends_file):
            print(Fore.RED + f"\n[✗] {self.friends_file} not found!")
            return []
        
        with open(self.friends_file, 'r') as f:
            user_ids = [line.strip() for line in f if line.strip()]
        
        return user_ids
    
    def save_user_ids(self, user_ids):
        """Save user IDs to file"""
        with open(self.friends_file, 'w') as f:
            for user_id in user_ids:
                f.write(f"{user_id}\n")
    
    def apply_blacklist(self, user_ids, blacklist_input):
        """Remove blacklisted IDs from the list"""
        if not blacklist_input.strip():
            return user_ids
        
        blacklist = [id.strip() for id in blacklist_input.split(',') if id.strip()]
        
        if not blacklist:
            return user_ids
        
        # Save blacklist to file
        with open(self.blacklist_file, 'w') as f:
            for user_id in blacklist:
                f.write(f"{user_id}\n")
        
        # Filter out blacklisted IDs
        filtered_ids = [uid for uid in user_ids if uid not in blacklist]
        
        print(Fore.YELLOW + f"\n[i] Removed {len(user_ids) - len(filtered_ids)} blacklisted IDs")
        print(Fore.CYAN + f"[i] Remaining: {len(filtered_ids)} friends to process")
        
        return filtered_ids
    
    def remove_with_threads(self, user_ids, num_threads):
        """Remove friends using multiple threads with retry logic for failed IDs"""
        if not user_ids:
            print(Fore.RED + "\n[✗] No user IDs to process")
            return
        
        current_ids = user_ids.copy()
        total_original = len(current_ids)
        round_num = 1
        total_successful = 0
        total_failed = 0
        
        print(Fore.BLUE + f"\n[*] Starting removal with {num_threads} threads")
        print(Fore.BLUE + f"[*] Total friends to remove: {total_original}")
        
        # Continue until no failed IDs remain
        while current_ids:
            print(Fore.MAGENTA + f"\n{'='*50}")
            print(Fore.MAGENTA + f"ROUND {round_num} - Processing {len(current_ids)} friends")
            print(Fore.MAGENTA + f"{'='*50}")
            
            successful = 0
            failed = 0
            failed_ids = []
            failed_reasons = {}
            
            # Use ThreadPoolExecutor for multithreading
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                # Submit all tasks
                future_to_user = {}
                for user_id in current_ids:
                    future = executor.submit(self.remove_friend, user_id)
                    future_to_user[future] = user_id
                
                # Process completed tasks
                for future in as_completed(future_to_user):
                    user_id = future_to_user[future]
                    try:
                        success, reason = future.result()
                        if success:
                            successful += 1
                            print(Fore.GREEN + f"[✓] Removed friend: {user_id}")
                        else:
                            failed += 1
                            failed_ids.append(user_id)
                            failed_reasons[user_id] = reason
                            print(Fore.RED + f"[✗] Failed to remove {user_id} ({reason})")
                    except Exception as e:
                        failed += 1
                        failed_ids.append(user_id)
                        failed_reasons[user_id] = str(e)
                        print(Fore.RED + f"[✗] Exception for {user_id}: {e}")
                    
                    # Small random delay to avoid rate limits
                    time.sleep(random.uniform(0.1, 0.3))
            
            # Update totals
            total_successful += successful
            total_failed += failed
            
            # Show round results
            print(Fore.CYAN + f"\n[Round {round_num} Results]")
            print(Fore.GREEN + f"  Successful: {successful}")
            print(Fore.RED + f"  Failed: {failed}")
            
            if failed_ids:
                print(Fore.YELLOW + f"\n  Failed IDs: {', '.join(failed_ids[:5])}" + ("..." if len(failed_ids) > 5 else ""))
                
                # Group failures by reason
                reason_groups = {}
                for uid in failed_ids:
                    reason = failed_reasons[uid]
                    if reason not in reason_groups:
                        reason_groups[reason] = []
                    reason_groups[reason].append(uid)
                
                print(Fore.YELLOW + "\n  Failure reasons:")
                for reason, ids in reason_groups.items():
                    print(Fore.YELLOW + f"    • {reason}: {len(ids)} IDs")
            
            # Prepare for next round if there are failed IDs
            if failed_ids and len(failed_ids) < len(current_ids):
                current_ids = failed_ids
                round_num += 1
                print(Fore.YELLOW + f"\n[*] Retrying {len(failed_ids)} failed IDs in next round...")
                time.sleep(2)  # Wait before next round
            elif failed_ids and len(failed_ids) == len(current_ids):
                print(Fore.RED + "\n[!] All IDs failed in this round. Stopping to avoid infinite loop.")
                print(Fore.YELLOW + "[!] This might indicate a token issue or rate limiting.")
                break
            else:
                current_ids = []  # All successful, exit loop
        
        print(Fore.MAGENTA + f"\n{'='*50}")
        print(Fore.MAGENTA + "FINAL RESULTS")
        print(Fore.MAGENTA + f"{'='*50}")
        print(Fore.GREEN + f"[✓] Successfully removed: {total_successful}")
        print(Fore.RED + f"[✗] Failed: {total_failed}")
        print(Fore.CYAN + f"[i] Total rounds: {round_num}")
        print(Fore.CYAN + f"[i] Original total: {total_original}")


def main():
    setTitle("Discord Friend Remover")
    clear()
    
    # Print logo
    print(Fore.GREEN + logo)
    
    # Get Discord token
    print(Fore.BLUE + "\n[?] Enter your Discord token:")
    token = input(Fore.RED + "Token: " + Fore.WHITE).strip()
    
    if not token:
        print(Fore.RED + "[✗] Token cannot be empty!")
        input(Fore.BLUE + "\nPress Enter to exit...")
        return
    
    # Initialize the remover
    remover = DiscordFriendRemover(token)
    
    if not remover.session:
        print(Fore.RED + "[✗] Failed to initialize session!")
        input(Fore.BLUE + "\nPress Enter to exit...")
        return
    
    # Step 1: Fetch and save friends
    friends = remover.get_friends()
    
    if not friends:
        print(Fore.RED + "[✗] Failed to fetch friends. Check your token and try again.")
        input(Fore.BLUE + "\nPress Enter to exit...")
        return
    
    # Step 2: Load user IDs from file
    user_ids = remover.load_user_ids()
    
    if not user_ids:
        print(Fore.RED + "[✗] No user IDs found in file!")
        input(Fore.BLUE + "\nPress Enter to exit...")
        return
    
    # Step 3: Ask for thread count
    print(Fore.BLUE + "\n" + "="*50)
    while True:
        try:
            num_threads = int(input(Fore.CYAN + "[?] How many threads to use? (1-20): " + Fore.WHITE).strip())
            if 1 <= num_threads <= 20:
                break
            else:
                print(Fore.RED + "[!] Please enter a number between 1 and 20")
        except ValueError:
            print(Fore.RED + "[!] Please enter a valid number")
    
    # Step 4: Ask for blacklist
    print(Fore.YELLOW + "\n[?] Enter user IDs to blacklist (comma-separated, or press Enter to skip):")
    blacklist_input = input(Fore.CYAN + "Blacklist: " + Fore.WHITE).strip()
    
    # Apply blacklist
    user_ids = remover.apply_blacklist(user_ids, blacklist_input)
    
    # Save filtered list
    remover.save_user_ids(user_ids)
    
    # Step 5: Confirm and start
    print(Fore.BLUE + "\n" + "="*50)
    print(Fore.CYAN + f"[i] Ready to remove {len(user_ids)} friends with {num_threads} threads")
    confirm = input(Fore.GREEN + "[?] Start the process? (yes/no): " + Fore.WHITE).strip().lower()
    
    if confirm in ['yes', 'y']:
        remover.remove_with_threads(user_ids, num_threads)
    else:
        print(Fore.YELLOW + "[i] Operation cancelled")
    
    print(Fore.GREEN + "\n[✓] Program finished!")
    input(Fore.BLUE + "\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        # Check if required packages are installed
        try:
            import tls_client
        except ImportError:
            print(Fore.YELLOW + "Installing required package: tls-client...")
            os.system("pip install tls-client")
            import tls_client
        
        main()
    except KeyboardInterrupt:
        print(Fore.RED + "\n\n[!] Program interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(Fore.RED + f"\n[!] Unexpected error: {e}")
        sys.exit(1)