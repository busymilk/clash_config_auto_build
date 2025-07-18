# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - AWS IP检测版地理位置检测器
使用 AWS checkip 服务检测代理出口IP，支持IPv4和IPv6
"""

import requests
import time
import urllib.parse
from typing import Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .logger import setup_logger


class AWSGeoIPDetector:
    """AWS IP检测版地理位置检测器"""
    
    def __init__(self):
        self.logger = setup_logger("aws_geoip_detector")
        
        # AWS IP检测服务 (支持IPv4和IPv6)
        self.ip_services = {
            'ipv4': 'https://checkip.amazonaws.com/',
            'ipv6': 'https://checkipv6.amazonaws.com/'
        }
        
        # 多个GeoIP服务API，提供冗余
        self.geoip_services = [
            {
                'name': 'ipapi.co',
                'url': 'https://ipapi.co/{ip}/json/',
                'country_field': 'country_code',
                'city_field': 'city',
                'region_field': 'region'
            },
            {
                'name': 'ip-api.com',
                'url': 'http://ip-api.com/json/{ip}',
                'country_field': 'countryCode',
                'city_field': 'city',
                'region_field': 'regionName'
            },
            {
                'name': 'ipinfo.io',
                'url': 'https://ipinfo.io/{ip}/json',
                'country_field': 'country',
                'city_field': 'city',
                'region_field': 'region'
            }
        ]
        
        # 地区代码映射
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
            'FR': {'code': 'FR', 'name': '法国', 'emoji': '🇫🇷'},
            'NL': {'code': 'NL', 'name': '荷兰', 'emoji': '🇳🇱'},
            'RU': {'code': 'RU', 'name': '俄罗斯', 'emoji': '🇷🇺'},
            'IN': {'code': 'IN', 'name': '印度', 'emoji': '🇮🇳'},
            'TH': {'code': 'TH', 'name': '泰国', 'emoji': '🇹🇭'},
            'MY': {'code': 'MY', 'name': '马来西亚', 'emoji': '🇲🇾'},
            'PH': {'code': 'PH', 'name': '菲律宾', 'emoji': '🇵🇭'},
            'VN': {'code': 'VN', 'name': '越南', 'emoji': '🇻🇳'},
            'ID': {'code': 'ID', 'name': '印尼', 'emoji': '🇮🇩'},
            'TR': {'code': 'TR', 'name': '土耳其', 'emoji': '🇹🇷'},
            'AR': {'code': 'AR', 'name': '阿根廷', 'emoji': '🇦🇷'},
            'BR': {'code': 'BR', 'name': '巴西', 'emoji': '🇧🇷'},
            'MX': {'code': 'MX', 'name': '墨西哥', 'emoji': '🇲🇽'},
        }
        
        # 城市特殊映射
        self.city_mapping = {
            'Hong Kong': 'HK',
            'Taipei': 'TW',
            'Seoul': 'KR',
            'Tokyo': 'JP',
            'Osaka': 'JP',
            'Singapore': 'SG',
            'London': 'GB',
            'New York': 'US',
            'Los Angeles': 'US',
            'San Francisco': 'US',
            'Chicago': 'US',
            'Dallas': 'US',
            'Miami': 'US',
            'Seattle': 'US',
            'Toronto': 'CA',
            'Vancouver': 'CA',
            'Sydney': 'AU',
            'Melbourne': 'AU',
            'Frankfurt': 'DE',
            'Berlin': 'DE',
            'Amsterdam': 'NL',
            'Paris': 'FR',
            'Moscow': 'RU',
            'Mumbai': 'IN',
            'Bangkok': 'TH',
            'Kuala Lumpur': 'MY',
            'Manila': 'PH',
            'Ho Chi Minh City': 'VN',
            'Jakarta': 'ID',
            'Istanbul': 'TR',
        }
    
    def get_proxy_exit_ip(self, proxy_name: str, api_url: str = "127.0.0.1:9090", 
                         timeout: int = 15) -> Optional[str]:
        """
        通过代理获取出口IP地址
        
        Args:
            proxy_name: 代理名称
            api_url: mihomo API地址
            timeout: 超时时间(秒)
            
        Returns:
            出口IP地址，失败返回None
        """
        try:
            # 第一步：切换到指定代理
            switch_url = f"http://{api_url}/proxies/GLOBAL"
            switch_data = {"name": proxy_name}
            
            response = requests.put(
                switch_url, 
                json=switch_data, 
                timeout=5,
                headers={'Content-Type': 'application/json; charset=utf-8'}
            )
            if response.status_code != 204:
                self.logger.warning(f"切换代理 '{proxy_name}' 失败: {response.status_code}")
                return None
            
            # 等待代理切换生效
            time.sleep(3)
            
            # 第二步：通过代理访问AWS IP检测服务
            proxy_url = f"http://127.0.0.1:7890"  # mihomo的mixed-port
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # 优先尝试IPv4，然后尝试IPv6
            for ip_version, service_url in self.ip_services.items():
                try:
                    response = requests.get(
                        service_url,
                        proxies=proxies,
                        timeout=timeout,
                        headers={'User-Agent': 'ClashConfigAutoBuilder/1.0'}
                    )
                    
                    if response.status_code == 200:
                        ip = response.text.strip()
                        if self._is_valid_ip(ip):
                            self.logger.info(f"代理 '{proxy_name}' 出口IP: {ip} ({ip_version})")
                            return ip
                        else:
                            self.logger.debug(f"AWS {ip_version} 返回无效IP: {ip}")
                            continue
                    else:
                        self.logger.debug(f"AWS {ip_version} 响应异常: {response.status_code}")
                        continue
                        
                except Exception as e:
                    self.logger.debug(f"AWS {ip_version} 检测失败: {e}")
                    continue
            
            self.logger.warning(f"无法获取代理 '{proxy_name}' 的出口IP")
            return None
            
        except requests.exceptions.ProxyError as e:
            self.logger.warning(f"代理 '{proxy_name}' 连接失败: {e}")
            return None
        except requests.exceptions.Timeout as e:
            self.logger.warning(f"代理 '{proxy_name}' 请求超时: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取代理 '{proxy_name}' 出口IP时发生错误: {e}")
            return None
    
    def _is_valid_ip(self, ip: str) -> bool:
        """验证IP地址格式（支持IPv4和IPv6）"""
        try:
            # IPv4 验证
            if '.' in ip:
                parts = ip.split('.')
                return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
            # IPv6 验证
            elif ':' in ip:
                # 简单的IPv6格式验证
                return len(ip.split(':')) >= 3 and all(c in '0123456789abcdefABCDEF:' for c in ip)
            else:
                return False
        except:
            return False
    
    def get_ip_location(self, ip: str) -> Optional[Dict]:
        """获取IP地址的地理位置信息"""
        for service in self.geoip_services:
            try:
                url = service['url'].format(ip=ip)
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # 提取地理位置信息
                    country_code = data.get(service['country_field'], '').upper()
                    city = data.get(service['city_field'], '')
                    region = data.get(service['region_field'], '')
                    
                    if country_code:
                        location_info = {
                            'country_code': country_code,
                            'city': city,
                            'region': region,
                            'service': service['name']
                        }
                        
                        self.logger.info(f"IP {ip} 地理位置: {country_code} {city} (来源: {service['name']})")
                        return location_info
                        
            except Exception as e:
                self.logger.debug(f"GeoIP服务 {service['name']} 查询失败: {e}")
                continue
        
        self.logger.warning(f"无法获取IP {ip} 的地理位置信息")
        return None
    
    def generate_node_name(self, original_name: str, location_info: Dict, 
                          include_original: bool = True) -> str:
        """根据地理位置信息生成新的节点名称"""
        country_code = location_info.get('country_code', '').upper()
        city = location_info.get('city', '')
        
        # 优先使用城市映射
        if city in self.city_mapping:
            mapped_country = self.city_mapping[city]
            if mapped_country in [info['code'] for info in self.country_mapping.values()]:
                country_code = mapped_country
        
        # 获取国家信息
        country_info = None
        for code, info in self.country_mapping.items():
            if code == country_code or info['code'] == country_code:
                country_info = info
                break
        
        if not country_info:
            # 未知地区，保持原名
            return original_name
        
        # 生成新名称
        emoji = country_info['emoji']
        country_name = country_info['name']
        
        # 构建地区标识
        if city and city != country_name:
            location_str = f"{emoji} {country_name}-{city}"
        else:
            location_str = f"{emoji} {country_name}"
        
        # 是否包含原始名称
        if include_original:
            # 清理原始名称中的地区标识
            cleaned_name = self._clean_original_name(original_name)
            if cleaned_name:
                new_name = f"{location_str} {cleaned_name}"
            else:
                new_name = location_str
        else:
            new_name = location_str
        
        return new_name
    
    def _clean_original_name(self, name: str) -> str:
        """清理原始名称中的地区标识和emoji"""
        import re
        
        # 移除emoji
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # 国旗
            "\U0001F300-\U0001F5FF"  # 符号和象形文字
            "\U0001F600-\U0001F64F"  # 表情符号
            "\U0001F680-\U0001F6FF"  # 交通和地图符号
            "\U0001F700-\U0001F77F"  # 炼金术符号
            "\U0001F780-\U0001F7FF"  # 几何形状扩展
            "\U0001F800-\U0001F8FF"  # 补充箭头-C
            "\U0001F900-\U0001F9FF"  # 补充符号和象形文字
            "\U0001FA00-\U0001FA6F"  # 棋类符号
            "\U0001FA70-\U0001FAFF"  # 符号和象形文字扩展-A
            "\U00002702-\U000027B0"  # 装饰符号
            "\U000024C2-\U0001F251"
            "]+"
        )
        
        cleaned = emoji_pattern.sub('', name)
        
        # 移除常见的地区标识
        region_patterns = [
            r'\b(HK|Hong[\s_-]?Kong|香港)\b',
            r'\b(US|USA|America|United[\s_-]?States|美国)\b',
            r'\b(JP|Japan|Tokyo|日本)\b',
            r'\b(UK|England|Britain|United[\s_-]?Kingdom|英国)\b',
            r'\b(SG|Singapore|新加坡)\b',
            r'\b(TW|Taiwan|Taipei|台湾)\b',
            r'\b(KR|Korea|Seoul|韩国)\b',
            r'\b(DE|Germany|Berlin|德国)\b',
            r'\b(CA|Canada|加拿大)\b',
            r'\b(AU|Australia|澳大利亚)\b',
        ]
        
        for pattern in region_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # 清理多余的空格和符号
        cleaned = re.sub(r'[\s\-_]+', ' ', cleaned).strip()
        cleaned = re.sub(r'^[\s\-_]+|[\s\-_]+$', '', cleaned)
        
        return cleaned
    
    def detect_and_rename_nodes(self, proxies: list, api_url: str = "127.0.0.1:9090",
                               max_workers: int = 3, timeout: int = 20) -> list:
        """批量检测节点地理位置并重新命名"""
        self.logger.info(f"开始检测 {len(proxies)} 个节点的地理位置...")
        
        renamed_proxies = []
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有检测任务
            future_to_proxy = {
                executor.submit(
                    self._detect_single_node, 
                    proxy, 
                    api_url, 
                    timeout
                ): proxy 
                for proxy in proxies
            }
            
            # 收集结果
            for future in as_completed(future_to_proxy):
                processed_count += 1
                original_proxy = future_to_proxy[future]
                
                try:
                    result_proxy = future.result()
                    if result_proxy:
                        renamed_proxies.append(result_proxy)
                    else:
                        # 检测失败，保持原名
                        renamed_proxies.append(original_proxy)
                        
                except Exception as e:
                    self.logger.error(f"处理节点 '{original_proxy.get('name')}' 时发生错误: {e}")
                    renamed_proxies.append(original_proxy)
                
                # 进度报告
                if processed_count % 10 == 0:
                    self.logger.info(f"已处理 {processed_count}/{len(proxies)} 个节点")
        
        renamed_count = len([p for p in renamed_proxies if p.get('_renamed')])
        self.logger.info(f"地理位置检测完成！成功重命名 {renamed_count}/{len(proxies)} 个节点")
        return renamed_proxies
    
    def _detect_single_node(self, proxy: dict, api_url: str, timeout: int) -> Optional[dict]:
        """检测单个节点的地理位置"""
        proxy_name = proxy.get('name')
        if not proxy_name:
            return proxy
        
        try:
            # 获取出口IP
            exit_ip = self.get_proxy_exit_ip(proxy_name, api_url, timeout)
            if not exit_ip:
                return proxy
            
            # 获取地理位置
            location_info = self.get_ip_location(exit_ip)
            if not location_info:
                return proxy
            
            # 生成新名称
            new_name = self.generate_node_name(proxy_name, location_info)
            
            # 创建新的代理对象
            new_proxy = proxy.copy()
            new_proxy['name'] = new_name
            new_proxy['_original_name'] = proxy_name
            new_proxy['_exit_ip'] = exit_ip
            new_proxy['_location'] = location_info
            new_proxy['_renamed'] = True
            
            self.logger.info(f"节点重命名: '{proxy_name}' -> '{new_name}'")
            return new_proxy
            
        except Exception as e:
            self.logger.error(f"检测节点 '{proxy_name}' 地理位置失败: {e}")
            return proxy