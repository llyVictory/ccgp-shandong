import requests
import json
import sys

def test_proxy():
    # 您的代理配置
    proxies = {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }
    
    test_url = "https://httpbin.org/ip"
    
    print("="*40)
    print("      Clash 代理生效自动化测试 (V2)")
    print("="*40)
    
    # 1. 强制纯净直连 (忽略环境变量)
    print("\n[步骤 1] 正在发起“纯净”直连请求 (忽略环境变量)...")
    ip_direct = None
    try:
        session_direct = requests.Session()
        session_direct.trust_env = False # 关键：不读取系统环境变量
        response_direct = session_direct.get(test_url, timeout=10)
        ip_direct = response_direct.json().get("origin")
        print(f"   >>> 纯净直连获取的 IP: {ip_direct}")
    except Exception as e:
        print(f"   ⚠️ 直连测试失败: {e}")

    # 2. 指定代理连接
    print(f"\n[步骤 2] 正在通过显式代理发起请求 (Port: {proxies['http']})...")
    ip_proxy = None
    try:
        # 这里显式传入 proxies
        response_proxy = requests.get(test_url, proxies=proxies, timeout=10)
        ip_proxy = response_proxy.json().get("origin")
        print(f"   >>> 显式代理获取的 IP: {ip_proxy}")
    except Exception as e:
        print(f"   ❌ 代理连接失败 (连接 7897 端口超时或拒绝)")
        print(f"   原因: {e}")
        return
    except Exception as e:
        print(f"   ❌ 代理连接失败！")
        print(f"   原因: {e}")
        print("\n检查建议:")
        print("1. 确保 Clash 软件已启动。")
        print("2. 检查 Clash 设置 -> 混合端口 (Mixed Port) 或 HTTP 端口是否真的是 7897。")
        print("3. 如果是初次使用，请确保安全软件没有拦截 Python 访问本地端口。")
        return

    # 3. 结果汇总与逻辑判定
    print("\n" + "="*40)
    print("              判定结果")
    print("="*40)
    
    if ip_direct and ip_proxy:
        if ip_direct != ip_proxy:
            print("🟢 状态: 代理生效 (SUCCESS)")
            print(f"   - 真实网络出口: {ip_direct}")
            print(f"   - 代理网络出口: {ip_proxy}")
        else:
            print("🟡 状态: 代理配置已载入但未走代理 (BYPASS)")
            print("   原因分析:")
            print("   - 您可能在 Clash 中开启了 '规则 (Rule)' 模式，且 httpbin.org 被分流到了 'Direct'。")
            print("   - 解决方法: 请尝试将 Clash 切换为 '全局 (Global)' 模式后再运行此脚本。")
    else:
        print("🔴 状态: 测试不完整，请检查网络连接。")
    print("="*40)

if __name__ == "__main__":
    test_proxy()
