# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - GeoIP Detector
Uses mihomo's content_check API for IP detection and a local database for GeoIP mapping.
"""

import os
import requests
import urllib.parse
from typing import Dict, Optional, List

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
            if country_code:
                location_info = {'country_code': country_code.upper()}
                self.logger.info(f"IP {ip} location: {country_code} (from local DB)")
                return location_info
        except geoip2.errors.AddressNotFoundError:
            self.logger.debug(f"IP {ip} not found in local GeoIP database.")
        except Exception as e:
            self.logger.error(f"Local GeoIP lookup for {ip} failed: {e}")
        
        return None

    def generate_node_name(self, original_name: str, location_info: Dict) -> str:
        """Generate new node name based on location."""
        country_code = location_info.get('country_code', '').upper()
        country_info = self.country_mapping.get(country_code)

        if not country_info:
            return original_name

        emoji = country_info['emoji']
        country_name = country_info['name']
        location_str = f"{emoji} {country_name}"
        
        return f"{location_str} {original_name}"

    def detect_and_rename_nodes(self, proxies: List[Dict], api_url: str, timeout: int, **kwargs) -> List[Dict]:
        """Batch detect and rename nodes using a single content_check API call."""
        self.logger.info(f"Starting batch GeoIP detection for {len(proxies)} nodes...")

        if not proxies:
            return []

        # Create a map of original names to proxy objects for easy lookup
        proxy_map = {p['name']: p for p in proxies}

        # Construct the batch check URL
        proxy_names_str = '|'.join(urllib.parse.quote(p['name']) for p in proxies)
        batch_check_url = f"http://{api_url}/proxies/{proxy_names_str}/check?url={urllib.parse.quote(self.ip_check_url)}"

        try:
            response = requests.get(batch_check_url, timeout=timeout)
            response.raise_for_status()
            results = response.json().get('results', [])
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Batch content_check API call failed: {e}")
            return proxies # Return original proxies on failure
        except ValueError: # JSONDecodeError
            self.logger.error("Failed to decode JSON response from batch content_check API.")
            return proxies

        renamed_proxies = []
        renamed_count = 0

        for result in results:
            proxy_name = result.get('proxy')
            original_proxy = proxy_map.get(proxy_name)

            if not original_proxy:
                self.logger.warning(f"Proxy '{proxy_name}' from API response not found in original list.")
                continue

            exit_ip = result.get('content')
            error = result.get('error')

            if error or not self._is_valid_ip(exit_ip):
                if error:
                    self.logger.debug(f"Proxy '{proxy_name}' failed check: {error}")
                new_proxy = original_proxy.copy()
                new_proxy['name'] = f"未知 {proxy_name}"
                renamed_proxies.append(new_proxy)
                continue

            location_info = self.get_ip_location(exit_ip)
            if not location_info:
                new_proxy = original_proxy.copy()
                new_proxy['name'] = f"未知 {proxy_name}"
                renamed_proxies.append(new_proxy)
                continue

            new_name = self.generate_node_name(proxy_name, location_info)
            
            new_proxy = original_proxy.copy()
            new_proxy['name'] = new_name
            new_proxy['_original_name'] = proxy_name
            new_proxy['_exit_ip'] = exit_ip
            new_proxy['_location'] = location_info
            new_proxy['_renamed'] = True
            
            self.logger.info(f"Node renamed: '{proxy_name}' -> '{new_name}'")
            renamed_proxies.append(new_proxy)
            renamed_count += 1

        self.logger.info(f"GeoIP detection complete. Renamed {renamed_count}/{len(proxies)} nodes.")
        return renamed_proxies

    def __del__(self):
        """Clean up resources."""
        if self.city_reader:
            self.city_reader.close()
