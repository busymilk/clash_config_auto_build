# -*- coding: utf-8 -*-
"""
Clash Config Auto Builder - 统一日志工具
提供标准化的日志记录功能
"""

import logging
import sys
from core.constants import LogConfig


def setup_logger(name: str, level: str = None) -> logging.Logger:
    """
    设置标准化的日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别，默认使用配置文件中的级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 设置日志级别
    log_level = level or LogConfig.LEVEL
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # 设置日志格式
    formatter = logging.Formatter(LogConfig.FORMAT)
    console_handler.setFormatter(formatter)
    
    # 添加处理器到日志记录器
    logger.addHandler(console_handler)
    
    return logger


def log_info(message: str, logger_name: str = "default"):
    """快捷信息日志"""
    logger = setup_logger(logger_name)
    logger.info(message)


def log_error(message: str, logger_name: str = "default"):
    """快捷错误日志"""
    logger = setup_logger(logger_name)
    logger.error(message)


def log_warning(message: str, logger_name: str = "default"):
    """快捷警告日志"""
    logger = setup_logger(logger_name)
    logger.warning(message)


def log_debug(message: str, logger_name: str = "default"):
    """快捷调试日志"""
    logger = setup_logger(logger_name)
    logger.debug(message)