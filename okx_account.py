import ccxt
import json
from dotenv import load_dotenv
import os
from flask import Flask, request, jsonify
from time import time
import time as time_module  # 添加这行来正确导入time模块
import socket
import secrets
import string
from wechat_bot import bot

def generate_strong_secret_key(length=32):
    """生成强随机密钥"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def update_env_secret_key(new_secret_key):
    """更新.env文件中的FLASK_SECRET_KEY"""
    env_content = []
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            env_content = f.readlines()
    except FileNotFoundError:
        pass
    
    secret_key_found = False
    for i, line in enumerate(env_content):
        if line.startswith('FLASK_SECRET_KEY='):
            env_content[i] = f'FLASK_SECRET_KEY={new_secret_key}\n'
            secret_key_found = True
            break
    
    if not secret_key_found:
        env_content.append(f'FLASK_SECRET_KEY={new_secret_key}\n')
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.writelines(env_content)

# 加载.env文件中的环境变量
load_dotenv(override=True)

# 从环境变量获取配置
api_key = os.getenv('API_KEY')
secret = os.getenv('SECRET')
password = os.getenv('PASSWORD')
use_proxy = int(os.getenv('USE_PROXY', 0))
http_proxy = os.getenv('HTTP_PROXY')
https_proxy = os.getenv('HTTPS_PROXY')

# Flask 配置
flask_secret_key = generate_strong_secret_key()  # 每次启动生成新密钥
update_env_secret_key(flask_secret_key)  # 更新到 .env 文件
flask_host = os.getenv('FLASK_HOST', '127.0.0.1')  # 默认监听 127.0.0.1 
flask_port = int(os.getenv('PORT', os.getenv('FLASK_PORT', 5000)))

# 添加新的全局配置
trade_type = os.getenv('TRADE_TYPE', 'spot')  # 默认现货
buy_order_type = os.getenv('BUY_ORDER_TYPE', 'market')  # 买入默认市价单
sell_order_type = os.getenv('SELL_ORDER_TYPE', 'limit')  # 卖出默认限价单

# 修改交易对配置读取部分
trade_symbols = os.getenv('TRADE_SYMBOLS', 'BTC/USDT').split(',')

# 根据配置设置代理
proxies = {
    'http': http_proxy,
    'https': https_proxy
} if use_proxy == 1 else None

# 创建OKX交易所实例
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret,
    'password': password,
    'proxies': proxies
})

# 创建 Flask 应用
app = Flask(__name__)

# 修改全局变量部分
last_alert = {
    "data": {},  # 改为字典,按symbol存储
    "timestamp": {},  # 改为字典,按symbol存储
    "executed_times": {}  # 保持不变,但内部结构会改变
}

# 可以添加清理旧记录的函数
def clean_old_records():
    global last_alert
    current_time = time()
    yesterday = current_time - 86400  # 24小时前
    
    # 为每个交易对清理旧记录
    for symbol in list(last_alert["executed_times"].keys()):
        last_alert["executed_times"][symbol] = {
            k: v for k, v in last_alert["executed_times"][symbol].items()
            if time_module.mktime(time_module.strptime(k, "%Y-%m-%dT%H:%M:%SZ")) > yesterday
        }

def place_order(action, symbol, amount, price=None):
    try:
        params = {
            'type': trade_type
        }
        
        # 获取当前时间
        current_time = time_module.strftime("%Y-%m-%d %H:%M:%S", time_module.localtime())
        
        # 根据买卖动作使用不同的下单方式
        if action == 'buy':
            if buy_order_type == 'limit' and price:
                order = exchange.create_order(
                    symbol=symbol,
                    type='limit',
                    side=action,
                    amount=amount,
                    price=price,
                    params=params
                )
            else:
                order = exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=action,
                    amount=amount,
                    params=params
                )
        else:  # action == 'sell'
            if sell_order_type == 'limit' and price:
                order = exchange.create_order(
                    symbol=symbol,
                    type='limit',
                    side=action,
                    amount=amount,
                    price=price,
                    params=params
                )
            else:
                order = exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side=action,
                    amount=amount,
                    params=params
                )
        
        # 修改打印格式，添加时间和订单类型
        order_type = '限价' if (action == 'buy' and buy_order_type == 'limit') or \
                              (action == 'sell' and sell_order_type == 'limit') else '市价'
        print(f"[{current_time}] 下单成功: {action} {amount} {symbol} @ {price if price else '市价'} ({order_type})")
        return order
    except Exception as e:
        print(f"下单失败: {str(e)}")
        raise e

@app.route('/webhook', methods=['POST'])
def webhook():
    global last_alert
    try:
        data = request.json
        print("收到的警报内容:", data)

        # 1. 验证密钥
        if data.get("secret") != flask_secret_key:
            print("无效的密钥")
            return jsonify({"error": "无效的密钥"}), 403

        # 2. 获取交易对和时间
        symbol = data.get('symbol')
        signal_time = data.get('time')
        
        # 初始化该交易对的执行记录
        if symbol not in last_alert["executed_times"]:
            last_alert["executed_times"][symbol] = {}
            last_alert["data"][symbol] = None
            last_alert["timestamp"][symbol] = 0

        # 检查是否为重复警报 - 使用时间戳作为唯一标识
        if signal_time in last_alert["executed_times"][symbol]:
            print(f"检测到重复警报 - {symbol}，详细信息：")
            print(f"信号时间: {signal_time}")
            print(f"上次执行时间: {last_alert['executed_times'][symbol][signal_time]}")
            return jsonify({
                "status": "ignored",
                "message": f"该时间戳的{symbol}信号已执行过",
                "signal_time": signal_time,
                "last_executed": last_alert['executed_times'][symbol][signal_time]
            }), 200

        # 3. 记录本次信号的执行时间
        current_time = time_module.strftime("%Y-%m-%d %H:%M:%S", time_module.localtime())
        last_alert["executed_times"][symbol][signal_time] = current_time
        last_alert["data"][symbol] = data
        last_alert["timestamp"][symbol] = time()

        # 4. 执行交易
        action = data.get('action')
        symbol = data.get('symbol')
        amount = float(data.get('amount'))
        price = float(data.get('price'))

        # 记录详细的交易信息
        print(f"\n新交易信号:")
        print(f"信号时间: {signal_time}")
        print(f"执行时间: {current_time}")
        print(f"交易方向: {action}")
        print(f"交易对: {symbol}")
        print(f"数量: {amount}")
        print(f"价格: {price}\n")

        # 根据action判断使用哪种下单方式
        use_price = None
        if (action == 'buy' and buy_order_type == 'limit') or \
           (action == 'sell' and sell_order_type == 'limit'):
            use_price = price

        try:
            # 下单
            order = place_order(action, symbol, amount, use_price)
            
            # 发送交易结果到企业微信
            bot.send_trade_info(
                signal_time=signal_time,
                current_time=current_time,
                action=action,
                symbol=symbol,
                amount=amount,
                price=price,
                order_result=order
            )
            
            response = {
                "message": "下单成功",
                "order": order,
                "order_type": buy_order_type if action == 'buy' else sell_order_type
            }
            return jsonify(response), 200

        except Exception as e:
            # 发送错误信息到企业微信
            bot.send_trade_info(
                signal_time=signal_time,
                current_time=current_time,
                action=action,
                symbol=symbol,
                amount=amount,
                price=price,
                error=str(e)
            )
            raise e

    except Exception as e:
        print(f"发生错误: {str(e)}")
        return jsonify({"error": str(e)}), 500

def check_port_available(host, port):
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            s.close()
            return True
        except OSError:
            return False

def find_available_port(start_port, end_port=65535):
    """查找可用端口"""
    for port in range(start_port, end_port + 1):
        if check_port_available(flask_host, port):
            return port
    return None

# 修改 alert_config 部分
def get_alert_configs():
    configs = {}
    for symbol in trade_symbols:
        configs[symbol] = {
            "ticker": "{{ticker}}",
            "exchange": "okx",
            "action": "{{strategy.order.action}}",
            "amount": "{{strategy.order.contracts}}",
            "price": "{{strategy.order.price}}", 
            "symbol": symbol,
            "secret": flask_secret_key,
            "time": "{{time}}",
            "interval": "{{interval}}"
        }
    return configs

# 在主程序开始处添加这段代码
if __name__ == '__main__':
    try:
        # 启动时已经生成了新密钥,这里不需要再生成
        load_dotenv(override=True)  # 重新加载环境变量

        # 获取本机IP地址
        def get_host_ip():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return '127.0.0.1'

        # 域名和端口配置逻辑
        is_production = os.getenv('FLASK_ENV', 'false').lower() == 'true'
        use_domain = os.getenv('USE_DOMAIN', 'false').lower() == 'true'
        domain = os.getenv('DOMAIN_NAME', '')
        use_https = os.getenv('USE_HTTPS', 'false').lower() == 'true'

        if is_production:
            if not use_domain:
                print("错误: 生产环境必须使用域名模式!")
                exit(1)
            webhook_url = f"https://{domain}/webhook"
            print(f"生产环境使用域名访问: {webhook_url}")
        else:
            if use_domain:
                webhook_url = f"{'https' if use_https else 'http'}://{domain}/webhook"
                print(f"开发环境使用域名访问: {webhook_url}")
            else:
                server_ip = get_host_ip()
                webhook_url = f"http://{server_ip}/webhook"
                print(f"开发环境使用IP访问: {webhook_url}")

        # 检查端口占用
        if not check_port_available(flask_host, flask_port):
            port_type = str(flask_port)
            if is_production:
                print(f"\n错误: 生产环境必需的{port_type}端口被占用!")
            else:
                print(f"\n错误: 当前配置需要使用{port_type}端口，但端口已被占用!")
            print("请关闭占用端口的程序后重试!")
            exit(1)

        # 在启动 Flask 应用之前打印账户余额
        print("正在获取账户余额...")
        balance = exchange.fetch_balance()
        print("账户余额:")
        for currency, details in balance['total'].items():
            print(f"{currency}: {details}")

        # 打印每个交易对的配置
        alert_configs = get_alert_configs()
        
        print("\n=== 交易信息 ===")
        for symbol in trade_symbols:
            print(f"\n--- {symbol} 配置 ---")
            print(f"1. 交易对: {symbol}")
            print(f"2. 买入类型: {'限价' if buy_order_type == 'limit' else '市价'}")
            print(f"3. 卖出类型: {'限价' if sell_order_type == 'limit' else '市价'}")
            
        print("\n=== TradingView 警报配置 ===")
        print("请为每个交易对配置单独的 TradingView 警报:")
        
        if use_domain:
            print(f"\nWebhook URL: {webhook_url}")
            print(f"域名模式，已配置到{flask_port}端口")
        else:
            print(f"\nWebhook URL: {webhook_url}")
            print(f"IP地址模式，已配置到{flask_port}端口")
        print("\n===========================")
        for symbol, config in alert_configs.items():
            print(f"\n--- {symbol} 警报消息内容 ---")
            print(json.dumps(config, indent=2, ensure_ascii=False))
        
        print("\n===========================")

        # 发送启动信息到企业微信
        bot.send_startup_info(
            balance=balance,
            trade_symbols=trade_symbols,
            buy_order_type=buy_order_type,
            sell_order_type=sell_order_type,
            webhook_url=webhook_url,
            use_domain=use_domain,
            alert_configs=alert_configs
        )

    except Exception as e:
        print(f"无法获取账户余额: {str(e)}")

    # 启动 Flask 应用
    print(f"\nAPI 服务正在启动: {webhook_url}")
    is_production = os.getenv('FLASK_ENV', 'false').lower() == 'true'
    
    # 修改启动逻辑部分
    if is_production and use_domain:
        try:
            from waitress import serve
            print("使用生产服务器(waitress)启动...")
            serve(app, host=flask_host, port=flask_port)
        except Exception as e:
            print(f"启动生产服务器失败: {str(e)}")
            print("尝试使用开发服务器启动...")
            app.run(host=flask_host, port=flask_port)
    else:
        print("使用开发服务器启动...")
        app.run(host=flask_host, port=flask_port)



