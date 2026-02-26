#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import os

def install_package(package):
    """安装Python包"""
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        print(f"✅ 已安装: {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装失败: {package} - {e}")
        return False

def main():
    print("Discord自动交易系统 - 依赖安装")
    print("=" * 50)
    
    required_packages = [
        'ibapi',  # Interactive Brokers API
    ]
    
    optional_packages = [
        'pandas',  # 数据分析
        'numpy',   # 数值计算
        'matplotlib',  # 图表
        'requests',    # HTTP请求
    ]
    
    print("🔧 安装必需的包...")
    success_count = 0
    
    for package in required_packages:
        if install_package(package):
            success_count += 1
    
    print(f"\\n✅ 必需包安装完成: {success_count}/{len(required_packages)}")
    
    if success_count < len(required_packages):
        print("❌ 某些必需包安装失败，可能影响交易功能")
    
    # 询问是否安装可选包
    install_optional = input("\\n是否安装可选包 (数据分析工具)? (y/N): ").lower() == 'y'
    
    if install_optional:
        print("\\n🔧 安装可选包...")
        for package in optional_packages:
            install_package(package)
    
    print("\\n🎉 依赖安装完成!")
    print("\\n📋 接下来的步骤:")
    print("1. 启动TWS (Trader Workstation)")
    print("2. 在TWS中启用API连接 (配置 -> API -> 启用ActiveX和Socket客户端)")
    print("3. 运行: python discord_trading_server.py")
    print("4. 启动Tampermonkey脚本开始监控")

if __name__ == "__main__":
    main()