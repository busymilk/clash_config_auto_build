# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - GeoIP Detector
Uses mihomo's content_check API for IP detection and a local database for GeoIP mapping.
"""

import os
import requests
import urllib.parse
from typing import Dict, Optional, List
import hashlib

try:
    import geoip2.database
    import geoip2.errors
    GEOIP2_AVAILABLE = True
except ImportError:
    GEOIP2_AVAILABLE = False

from .logger import setup_logger


class GeoIPDetector:
    """GeoIP Detector using batch content_check API"""

    def __init__(self):
        self.logger = setup_logger("geoip_detector")
        self.ip_check_url = "http://checkip.amazonaws.com/"

        # GeoIP database file path
        self.geoip_db_dir = "geoip_data"
        self.city_db_path = os.path.join(self.geoip_db_dir, "GeoLite2-City.mmdb")
        
        self.country_mapping = {
            'HK': {'code': 'HK', 'name': '香港', 'emoji': '🇭🇰'},
            'US': {'code': 'US', 'name': '美国', 'emoji': '🇺🇸'},
            'JP': {'code': 'JP', 'name': '日本', 'emoji': '🇯🇵'},
            'GB': {'code': 'UK', 'name': '英国', 'emoji': '🇬🇧'},
            'SG': {'code': 'SG', 'name': '新加坡', 'emoji': '🇸🇬'},
            'TW': {'code': 'TW', 'name': '台湾', 'emoji': '🇹🇼'},
            'KR': {'code': 'KR', 'name': '韩国', 'emoji': '🇰🇷'},
            'DE': {'code': 'DE', 'name': '德国', 'emoji': '🇩🇪'},
            'CA': {'code': 'CA', 'name': '加拿大', 'emoji': '🇨🇦'},
            'AU': {'code': 'AU', 'name': '澳大利亚', 'emoji': '🇦🇺'},
        }

        self.city_reader = None
        self._init_geoip_database()

    def _init_geoip_database(self):
        if not GEOIP2_AVAILABLE:
            self.logger.warning("geoip2 library not installed. GeoIP detection will be limited.")
            return
        
        if not os.path.exists(self.city_db_path):
            self.logger.warning(f"GeoIP database not found at {self.city_db_path}. Please run download_geoip_db.py.")
            return
        
        try:
            self.city_reader = geoip2.database.Reader(self.city_db_path)
            self.logger.info("GeoLite2-City database loaded successfully.")
        except Exception as e:
            self.logger.error(f"Failed to load GeoIP database: {e}")
            self.city_reader = None

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format (IPv4 and IPv6)."""
        if not ip or not isinstance(ip, str):
            return False
        if '.' in ip:
            parts = ip.split('.')
            return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
        elif ':' in ip:
            return True # Basic IPv6 check
        return False

    def get_ip_location(self, ip: str) -> Optional[Dict]:
        """Get IP location from local GeoIP database."""
        if not self.city_reader:
            self.logger.debug("GeoIP database not available, cannot get location.")
            return None
        
        try:
            response = self.city_reader.city(ip)
            country_code = response.country.iso_code
            city_name = response.city.name # Get city name
            if country_code:
                location_info = {
                    'country_code': country_code.upper(),
                    'city': city_name if city_name else '' # Include city name
                }
                self.logger.info(f"IP {ip} location: {country_code} {city_name} (from local DB)")
                return location_info
        except geoip2.errors.AddressNotFoundError:
            self.logger.debug(f"IP {ip} not found in local GeoIP database.")
        except Exception as e:
            self.logger.error(f"Local GeoIP lookup for {ip} failed: {e}")
        
        return None

    def generate_node_name(self, original_name: str, location_info: Dict) -> str:
        """Generate new node name based on location and a unique identifier."""
        country_code = location_info.get('country_code', '').upper()
        city_name = location_info.get('city', '') # Get city name
        country_info = self.country_mapping.get(country_code)

        # Generate a short unique identifier from the original name
        # Using SHA256 hash and taking the first 6 characters for brevity
        unique_id = hashlib.sha256(original_name.encode()).hexdigest()[:6]

        if not country_info:
            # If country info is not found, use "未知" and append unique_id
            return f"未知 ({unique_id})"

        emoji = country_info['emoji']
        country_name = country_info['name']

        # Construct the location string
        if city_name:
            location_str = f"{emoji} {country_name}-{city_name}"
        else:
            location_str = f"{emoji} {country_name}"
        
        # Combine location string with unique identifier
        return f"{location_str} ({unique_id})"

    def detect_and_rename_nodes(self, proxies: List[Dict], api_url: str, timeout: int, **kwargs) -> List[Dict]:
        """Batch detect and rename nodes using the /content_check endpoint."""
        self.logger.info(f"Starting batch GeoIP detection for {len(proxies)} nodes via /content_check...")

        if not proxies:
            return []

        # Create a map of original names to proxy objects for easy lookup
        proxy_map = {p['name']: p for p in proxies}
        
        # This will hold the final list of proxies, processed or not
        final_proxies = []
        
        # Keep track of which proxies have been processed by the API response
        processed_proxies = set()

        # Construct the correct URL for the batch content_check API
        encoded_check_url = urllib.parse.quote(self.ip_check_url)
        timeout_str = f"{timeout}s"
        batch_check_url = f"http://{api_url}/content_check?url={encoded_check_url}&timeout={timeout_str}"
        self.logger.info(f"Calling batch GeoIP API: {batch_check_url}")

        try:
            # The timeout for the requests call should be slightly longer than the API timeout
            response = requests.get(batch_check_url, timeout=timeout + 10)
            response.raise_for_status()
            results = response.json().get('results', [])
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Batch /content_check API call failed: {e}")
            # On total failure, rename all nodes to "未知" and return
            return [dict(p, name=f"未知 {p['name']}") for p in proxies]
        except (ValueError, AttributeError): # JSONDecodeError or if 'results' is not a list
            self.logger.error("Failed to decode or parse JSON response from /content_check API.")
            return [dict(p, name=f"未知 {p['name']}") for p in proxies]

        renamed_count = 0
        for result in results:
            proxy_name = result.get('proxy')
            original_proxy = proxy_map.get(proxy_name)

            if not original_proxy:
                self.logger.warning(f"Proxy '{proxy_name}' from API response not found in original list.")
                continue
            
            processed_proxies.add(proxy_name)
            exit_ip = result.get('content')
            error = result.get('error')

            # Case 1: Detection failed (error or invalid IP)
            if error or not self._is_valid_ip(exit_ip):
                if error:
                    self.logger.debug(f"Proxy '{proxy_name}' failed check: {error}")
                new_proxy = original_proxy.copy()
                new_proxy['name'] = f"未知 {proxy_name}"
                final_proxies.append(new_proxy)
                continue

            # Case 2: IP obtained, but GeoIP lookup failed
            location_info = self.get_ip_location(exit_ip)
            if not location_info:
                new_proxy = original_proxy.copy()
                new_proxy['name'] = f"未知 {proxy_name}"
                final_proxies.append(new_proxy)
                continue

            # Case 3: Success
            new_name = self.generate_node_name(proxy_name, location_info)
            new_proxy = original_proxy.copy()
            new_proxy['name'] = new_name
            new_proxy['_original_name'] = proxy_name
            new_proxy['_exit_ip'] = exit_ip
            new_proxy['_location'] = location_info
            new_proxy['_renamed'] = True
            
            self.logger.info(f"Node renamed: '{proxy_name}' -> '{new_name}'")
            final_proxies.append(new_proxy)
            renamed_count += 1
            
        # Add any proxies that were not in the API response back to the list
        for proxy in proxies:
            if proxy['name'] not in processed_proxies:
                self.logger.warning(f"Proxy '{proxy['name']}' was not present in the API response.")
                new_proxy = proxy.copy()
                new_proxy['name'] = f"未知 {proxy['name']}"
                final_proxies.append(new_proxy)

        self.logger.info(f"GeoIP detection complete. Renamed {renamed_count}/{len(proxies)} nodes.")
        return final_proxies

    def __del__(self):
        """Clean up resources."""
        if self.city_reader:
            self.city_reader.close()
