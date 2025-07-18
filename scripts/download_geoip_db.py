#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoIP数据库下载脚本
下载免费的GeoLite2数据库用于本地IP地理位置解析
"""

import os
import requests
import tarfile
import sys
from pathlib import Path

def download_geoip_databases():
    """下载GeoLite2数据库"""
    
    # 创建数据目录
    geoip_dir = Path("geoip_data")
    geoip_dir.mkdir(exist_ok=True)
    
    # 免费的GeoLite2数据库下载链接（不需要许可证密钥）
    # 注意：这些是第三方镜像，生产环境建议使用官方MaxMind数据库
    databases = {
        'city': {
            'url': 'https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb',
            'filename': 'GeoLite2-City.mmdb'
        },
        'country': {
            'url': 'https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb', 
            'filename': 'GeoLite2-Country.mmdb'
        }
    }
    
    for db_type, info in databases.items():
        db_path = geoip_dir / info['filename']
        
        # 检查文件是否已存在
        if db_path.exists():
            print(f"✅ {info['filename']} 已存在，跳过下载")
            continue
        
        print(f"📥 正在下载 {info['filename']}...")
        
        try:
            # 下载数据库文件
            response = requests.get(info['url'], stream=True, timeout=30)
            response.raise_for_status()
            
            # 保存文件
            with open(db_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"✅ {info['filename']} 下载完成")
            
        except Exception as e:
            print(f"❌ {info['filename']} 下载失败: {e}")
            if db_path.exists():
                db_path.unlink()  # 删除不完整的文件
            return False
    
    print("🎉 所有GeoIP数据库下载完成！")
    return True


def verify_databases():
    """验证数据库文件"""
    geoip_dir = Path("geoip_data")
    
    try:
        import geoip2.database
        
        # 验证城市数据库
        city_db = geoip_dir / "GeoLite2-City.mmdb"
        if city_db.exists():
            try:
                with geoip2.database.Reader(str(city_db)) as reader:
                    # 测试查询一个已知IP
                    response = reader.city('8.8.8.8')
                    print(f"✅ 城市数据库验证成功: {response.country.iso_code} {response.city.name}")
            except Exception as e:
                print(f"❌ 城市数据库验证失败: {e}")
                return False
        
        # 验证国家数据库
        country_db = geoip_dir / "GeoLite2-Country.mmdb"
        if country_db.exists():
            try:
                with geoip2.database.Reader(str(country_db)) as reader:
                    # 测试查询一个已知IP
                    response = reader.country('8.8.8.8')
                    print(f"✅ 国家数据库验证成功: {response.country.iso_code}")
            except Exception as e:
                print(f"❌ 国家数据库验证失败: {e}")
                return False
        
        return True
        
    except ImportError:
        print("⚠️ geoip2库未安装，无法验证数据库")
        return True


if __name__ == "__main__":
    print("🌍 GeoIP数据库下载工具")
    print("=" * 40)
    
    # 下载数据库
    if download_geoip_databases():
        # 验证数据库
        verify_databases()
        print("\n✅ 设置完成！现在可以使用本地GeoIP数据库进行地理位置解析。")
    else:
        print("\n❌ 下载失败，请检查网络连接后重试。")
        sys.exit(1)