import requests
import json
import time as time_module
import os
from dotenv import load_dotenv

class WeChatBot:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        self.webhook_url = os.getenv('WECHAT_BOT_URL')
        if not self.webhook_url:
            raise ValueError("企业微信机器人 webhook URL 未配置，请在 .env 文件中设置 WECHAT_BOT_URL")
        
        # 禁用所有代理设置
        os.environ['http_proxy'] = ''
        os.environ['https_proxy'] = ''
        os.environ['HTTP_PROXY'] = ''
        os.environ['HTTPS_PROXY'] = ''
        
        self.proxies = {
            'http': None,
            'https': None
        }
        
        # 设置 requests 的 SSL 验证
        self.verify = True

    def send_message(self, content):
        """发送文本消息到企业微信机器人"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        data = {
            "msgtype": "text",
            "text": {
                "content": content
            }
        }
        try:
            print(f"正在发送消息到企业微信...")
            
            # 使用显式的 session 来发送请求
            with requests.Session() as session:
                session.trust_env = False  # 禁用环境变量中的代理设置
                response = session.post(
                    self.webhook_url, 
                    headers=headers, 
                    json=data,
                    proxies=self.proxies,
                    verify=self.verify,
                    timeout=30
                )
            
            print(f"响应状态码: {response.status_code}")
            return response.json()
        except Exception as e:
            print(f"发送消息失败: {str(e)}")
            return None

    def send_startup_info(self, balance, trade_symbols, buy_order_type, sell_order_type, 
                         webhook_url, use_domain, alert_configs):
        """发送启动配置信息"""
        info = "=== OKX交易系统启动 ===\n\n"
        
        # 账户余额
        info += "账户余额:\n"
        for currency, details in balance['total'].items():
            info += f"{currency}: {details}\n"
        
        # 交易信息
        info += "\n=== 交易信息 ===\n"
        for symbol in trade_symbols:
            info += f"\n--- {symbol} 配置 ---\n"
            info += f"1. 交易对: {symbol}\n"
            info += f"2. 买入类型: {'限价' if buy_order_type == 'limit' else '市价'}\n"
            info += f"3. 卖出类型: {'限价' if sell_order_type == 'limit' else '市价'}\n"
        
        # Webhook配置
        info += "\n=== TradingView 警报配置 ===\n"
        info += f"\nWebhook URL: {webhook_url}\n"
        info += "域名模式，已配置到5000端口\n" if use_domain else "IP地址模式，已配置到80端口\n"
        
        # 警报配置
        info += "\n警报配置详情:\n"
        for symbol, config in alert_configs.items():
            info += f"\n--- {symbol} 警报消息内容 ---\n"
            info += f"{json.dumps(config, indent=2, ensure_ascii=False)}\n"

        # 发送消息并返回结果
        return self.send_message(info)

    def send_trade_info(self, signal_time, current_time, action, symbol, amount, price, 
                       order_result=None, error=None):
        """发送交易信息"""
        info = "=== 新交易信号 ===\n\n"
        info += f"信号时间: {signal_time}\n"
        info += f"执行时间: {current_time}\n"
        info += f"交易方向: {action}\n"
        info += f"交易对: {symbol}\n"
        info += f"数量: {amount}\n"
        info += f"价格: {price}\n"

        if error:
            info += f"\n下单失败!\n错误信息: {error}"
        elif order_result:
            info += f"\n下单成功!"

        return self.send_message(info)

# 创建机器人实例
bot = WeChatBot()